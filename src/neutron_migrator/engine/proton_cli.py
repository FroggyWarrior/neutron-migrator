"""Engine adapter backed by the official Proton Drive CLI (ProtonDriveApps/sdk).

Browser sign-in (CAPTCHA, 2FA, FIDO2 and two-password mode are handled by Proton's
web login), session stored in the OS secret store, all operations via --json.
"""
from __future__ import annotations

import json
import os
import queue
import shutil
import subprocess
import sys
import threading
import time
import platform
from collections import Counter, deque
from pathlib import Path

from .. import security
from ..errors import AppError, Cancelled
from .base import BatchResult, Photo, Progress, ScanResult, is_photo, is_video

BINARY = "proton-drive.exe" if os.name == "nt" else "proton-drive"
CHUNK = 40          # keeps argv well below the Windows 32k limit
POLL = 0.4


def _chunks(items: list, size: int):
    for index in range(0, len(items), size):
        yield items[index:index + size]


class ProtonCliEngine:
    def __init__(self, workdir: Path):
        self.workdir = workdir
        self.state_dir = workdir / "proton-cli"
        self.exe: Path | None = None
        self.version = "unknown"
        self.can_persist = True
        self.signed_in = False
        self._log: deque[str] = deque(maxlen=800)
        self._procs: set[subprocess.Popen] = set()
        self._lock = threading.Lock()
        self._account = ""

    # ------------------------------------------------------------- lifecycle
    def _find_exe(self) -> Path:
        candidates = []
        if os.environ.get("PROTON_DRIVE_CLI"):
            candidates.append(Path(os.environ["PROTON_DRIVE_CLI"]))
        candidates += [
            Path(__file__).resolve().parents[3] / "vendor" / "proton-drive" / BINARY,
            Path(sys.executable).resolve().parent / BINARY,
            Path(getattr(sys, "_MEIPASS", Path.cwd())) / BINARY,
        ]
        for candidate in candidates:
            if candidate.is_file():
                return candidate
        found = shutil.which("proton-drive")
        if found:
            return Path(found)
        raise AppError("error.cli_missing", debug=f"Searched: {[str(c) for c in candidates]} and PATH")

    def start(self) -> None:
        if self.exe:
            return
        self.exe = self._find_exe()
        self.state_dir.mkdir(parents=True, exist_ok=True)
        try:
            os.chmod(self.state_dir, 0o700)
        except OSError:
            pass
        try:
            out = self._run(["version"], timeout=120)
        except AppError as exc:
            raise AppError("error.cli_start", debug=exc.debug) from exc
        self.version = " ".join(out.split())[:120] or "unknown"

    def _env(self) -> dict[str, str]:
        env = dict(os.environ)
        env["PROTON_DRIVE_CACHE_DIR"] = str(self.state_dir)
        env["PROTON_DRIVE_LOG_LEVEL"] = "DEBUG"
        env["NO_COLOR"] = "1"
        return env

    def _popen(self, args: list[str]) -> subprocess.Popen:
        cmd = [str(self.exe), *args]
        paths = [a for a in args if a.startswith("/")]
        rest = [a for a in args if not a.startswith("/")]
        self._log.append("$ " + " ".join(rest) + (f" [{len(paths)} remote paths]" if paths else ""))
        proc = subprocess.Popen(  # noqa: S603
            cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
            encoding="utf-8", errors="replace", env=self._env(),
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
        with self._lock:
            self._procs.add(proc)
        return proc

    def _forget(self, proc) -> None:
        with self._lock:
            self._procs.discard(proc)

    @staticmethod
    def _terminate(proc) -> None:
        try:
            proc.terminate()
            proc.wait(timeout=5)
        except Exception:
            try:
                proc.kill()
            except Exception:
                pass

    @staticmethod
    def _pump(stream, sink) -> None:
        try:
            for line in stream:
                sink(line.rstrip("\n"))
        finally:
            try:
                stream.close()
            except Exception:
                pass

    def _run(self, args: list[str], timeout: float = 120) -> str:
        proc = self._popen(args)
        try:
            out, err = proc.communicate(timeout=timeout)
        except subprocess.TimeoutExpired:
            self._terminate(proc)
            out, err = proc.communicate()
            raise AppError("error.timeout", debug=f"Command: {' '.join(args)}") from None
        finally:
            self._forget(proc)
        self._log.extend((err or "").splitlines()[-40:])
        if proc.returncode != 0:
            raise AppError(
                "error.cli_command", message=(err or out or "").strip()[:300],
                debug=f"Command: {' '.join(args)}\nExit: {proc.returncode}\n"
                      f"stdout:\n{(out or '')[:4000]}\nstderr:\n{(err or '')[:4000]}",
            )
        return out or ""

    def _stream(self, args, cancel, on_line, on_tick=None, timeout=None) -> int:
        """Run a command, feeding each stdout line to on_line as it arrives."""
        proc = self._popen(args)
        lines: queue.Queue[str] = queue.Queue()
        readers = [
            threading.Thread(target=self._pump, args=(proc.stdout, lines.put), daemon=True),
            threading.Thread(target=self._pump, args=(proc.stderr, self._log.append), daemon=True),
        ]
        for reader in readers:
            reader.start()
        deadline = time.monotonic() + timeout if timeout else None
        try:
            while True:
                if cancel is not None and cancel.is_set():
                    self._terminate(proc)
                    raise Cancelled()
                if deadline and time.monotonic() > deadline:
                    self._terminate(proc)
                    raise AppError("error.timeout", debug=f"Command: {' '.join(args[:6])}")
                try:
                    line = lines.get(timeout=POLL)
                except queue.Empty:
                    if on_tick:
                        on_tick()
                    if proc.poll() is not None:
                        for reader in readers:
                            reader.join(timeout=5)
                        while not lines.empty():
                            on_line(lines.get_nowait())
                        break
                    continue
                on_line(line)
            return proc.wait(timeout=30)
        except BaseException:
            self._terminate(proc)
            raise
        finally:
            self._forget(proc)

    @staticmethod
    def _parse_item(line: str):
        text = line.strip().rstrip(",").strip()
        if not text or text in ("[", "]"):
            return None
        try:
            return json.loads(text)
        except ValueError:
            return None

    @staticmethod
    def _node_name(node: dict) -> str:
        name = node.get("name")
        if isinstance(name, dict):
            return name.get("value") or (name.get("error") or {}).get("name") or node.get("uid", "")
        return name or node.get("uid", "")

    @staticmethod
    def _node_size(node: dict) -> tuple[int, bool]:
        revision = node.get("activeRevision") or {}
        for source in (revision, node):
            for key in ("claimedSize", "size", "originalSize", "storageSize", "fileSize"):
                value = source.get(key)
                if isinstance(value, (int, float)) and value > 0:
                    return int(value), True
                if isinstance(value, str) and value.isdigit() and int(value) > 0:
                    return int(value), True
        return 0, False

    def log_tail(self, lines: int = 60) -> str:
        tail = list(self._log)[-lines:]
        for candidate in (self.state_dir / "proton-drive.log", self.state_dir / "Logs" / "proton-drive.log"):
            try:
                tail += ["", f"--- {candidate} ---", *candidate.read_text("utf-8", errors="replace").splitlines()[-lines:]]
                break
            except OSError:
                continue
        return "\n".join(tail)

    # ------------------------------------------------------------------ auth
    def login_via_browser(self, cancel, report) -> None:
        def on_line(line: str) -> None:
            data = self._parse_item(line)
            if isinstance(data, dict) and data.get("signInUrl"):
                report({"signInUrl": data["signInUrl"]})
            else:
                self._log.append(line)

        code = self._stream(["auth", "login", "--json"], cancel, on_line, timeout=1800)
        if code != 0:
            raise AppError("error.login_failed", debug=f"auth login exit={code}\n{self.log_tail(80)}")
        self.signed_in = True

    def has_saved_session(self) -> bool:
        try:
            self._run(["filesystem", "list", "/my-files", "--json"], timeout=180)
            self.signed_in = True
            return True
        except Exception:
            return False

    def resume(self) -> None:
        if not self.has_saved_session():
            raise AppError("error.not_signed_in", debug=self.log_tail(60))

    def sign_out(self) -> None:
        try:
            self._run(["auth", "logout"], timeout=120)
        except Exception:
            pass
        self.signed_in = False

    def shutdown(self, keep: bool) -> None:
        with self._lock:
            procs = list(self._procs)
        for proc in procs:
            self._terminate(proc)
        if not keep and self.signed_in:
            self.sign_out()
        self.signed_in = False

    def account_name(self) -> str:
        if self._account:
            return self._account
        email = ""
        try:
            out = self._run(["filesystem", "info", "/my-files", "--json"], timeout=180).strip()
            if out:
                email = self._find_email(json.loads(out.splitlines()[-1]))
        except Exception:
            email = ""
        if not email:
            for filename in ("config.json", "clientUid.json"):
                try:
                    email = self._find_email(json.loads((self.state_dir / filename).read_text("utf-8")))
                except (OSError, ValueError):
                    continue
                if email:
                    break
        self._account = email
        return email

    @staticmethod
    def _find_email(data) -> str:
        preferred = {"keyauthor", "claimedauthor", "email", "address", "username", "value"}
        found: list[tuple[int, str]] = []

        def walk(node, key: str = "") -> None:
            if isinstance(node, dict):
                for k, v in node.items():
                    walk(v, k.lower())
            elif isinstance(node, list):
                for item in node:
                    walk(item, key)
            elif isinstance(node, str) and "@" in node and " " not in node:
                domain = node.rsplit("@", 1)[-1]
                if "." in domain:
                    found.append((0 if key in preferred else 1, node))

        walk(data)
        found.sort(key=lambda item: item[0])
        return found[0][1] if found else ""

    # ----------------------------------------------------------------- drive
    def root_folders(self) -> list[str]:
        return []                      # the photo timeline is the scope

    def preferred_scope(self, folders: list[str]) -> str:
        return ""

    def scan(self, scope: str, cancel, include_videos: bool = False) -> ScanResult:
        photos: list[Photo] = []
        unknown = videos = video_bytes = 0
        samples: list[dict] = []

        def on_line(line: str) -> None:
            nonlocal unknown, videos, video_bytes
            node = self._parse_item(line)
            if not isinstance(node, dict) or "uid" not in node:
                return
            if len(samples) < 3:
                samples.append(node)
            name = self._node_name(node)
            size, known = self._node_size(node)
            if is_video(name) or node.get("type") == "video":
                videos += 1
                video_bytes += size
                if not include_videos:
                    return
            elif "." in name and not is_photo(name):
                return
            if not known:
                unknown += 1
            photos.append(Photo(path=node["uid"], size=size, name=name))

        code = self._stream(["photo", "timeline", "--json", "--load-details"], cancel, on_line, timeout=7200)
        if os.environ.get("NEUTRON_DEBUG_SCAN"):
            try:
                (self.state_dir / "scan-sample.json").write_text(
                    json.dumps(samples, indent=2, ensure_ascii=False), "utf-8")
            except OSError:
                pass
        if code != 0:
            raise AppError("error.scan_failed", debug=f"photo timeline exit={code}\n{self.log_tail(80)}")
        return ScanResult(sorted(photos, key=lambda p: p.name.lower()), unknown, videos, video_bytes)

    @staticmethod
    def _local_stats(folder: Path) -> tuple[int, int]:
        files = size = 0
        for root, _dirs, names in os.walk(folder, onerror=lambda _e: None):
            for name in names:
                try:
                    size += (Path(root) / name).stat().st_size
                    files += 1
                except OSError:
                    continue
        return files, size

    def download(self, photos: list[Photo], destination: Path, cancel, report, concurrency: int = 4) -> BatchResult:
        dest = Path(destination)
        dest.mkdir(parents=True, exist_ok=True)
        base_files, base_bytes = self._local_stats(dest)
        total, total_bytes = len(photos), sum(p.size for p in photos)
        done = skipped = transferred = 0
        failures: list[tuple[str, str]] = []
        cancelled = False
        history: deque[tuple[float, int]] = deque(maxlen=64)
        last_walk = [0.0, float(base_bytes)]

        def tick() -> None:
            now = time.monotonic()
            if now - last_walk[0] >= 1.0:
                last_walk[0] = now
                last_walk[1] = float(self._local_stats(dest)[1])
            got = max(0.0, last_walk[1] - base_bytes)
            history.append((now, got))
            while len(history) > 2 and now - history[0][0] > 10.0:
                history.popleft()
            speed = 0.0
            if len(history) >= 2:
                dt = history[-1][0] - history[0][0]
                db = history[-1][1] - history[0][1]
                if dt >= 1.0:
                    speed = max(0.0, db / dt)
            shown = min(got, total_bytes) if total_bytes else got
            remaining = max(0.0, total_bytes - shown)
            report(Progress(done_files=min(done + skipped, total), total_files=total,
                            done_bytes=int(shown), total_bytes=total_bytes,
                            speed=speed, eta=(remaining / speed) if speed > 0 else None))

        try:
            for chunk in _chunks(photos, CHUNK):
                if cancel.is_set():
                    raise Cancelled()
                summary: dict = {}

                def on_line(line: str) -> None:
                    data = self._parse_item(line)
                    if isinstance(data, dict) and "transferredItems" in data:
                        summary.update(data)
                    else:
                        self._log.append(line)

                args = ["photo", "download", *[f"/photos/{p.path}" for p in chunk], str(dest),
                        "--json", "--conflict-strategy", "rename"]
                code = self._stream(args, cancel, on_line, on_tick=tick, timeout=14400)
                if summary:
                    done += int(summary.get("transferredItems", 0))
                    skipped += int(summary.get("skippedItems", 0))
                    transferred += int(summary.get("transferredBytes", 0))
                    failures += [(f.get("name", "?"), str(f.get("error", ""))) for f in summary.get("failures", [])]
                elif code != 0:
                    raise AppError("error.download_failed", debug=f"photo download exit={code}\n{self.log_tail(100)}")
                tick()
        except Cancelled:
            cancelled = True
        return BatchResult("download", total, min(done + skipped, total), total_bytes,
                           transferred, failures, cancelled)

    def _node_command(self, command: str, paths: list[str], cancel, on_result) -> None:
        def on_line(line: str) -> None:
            data = self._parse_item(line)
            if isinstance(data, dict) and "uid" in data:
                on_result(data)
            else:
                self._log.append(line)

        code = self._stream(["filesystem", command, *paths, "--json"], cancel, on_line, timeout=3600)
        if code != 0:
            raise AppError("error.delete_failed", debug=f"filesystem {command} exit={code}\n{self.log_tail(100)}")

    def _trash_nodes(self, cancel) -> list[dict]:
        nodes: list[dict] = []

        def on_line(line: str) -> None:
            data = self._parse_item(line)
            if isinstance(data, dict) and "uid" in data:
                nodes.append(data)

        code = self._stream(["filesystem", "list", "/photos-trash", "--json"], cancel, on_line, timeout=1800)
        if code != 0:
            raise AppError("error.delete_failed", debug=f"list /photos-trash exit={code}\n{self.log_tail(80)}")
        return nodes

    def delete(self, photos: list[Photo], mode: str, cancel, report, concurrency: int = 4) -> BatchResult:
        permanent = mode == "permanent"
        total = len(photos)
        weight = {p.path: float(p.size or 1) for p in photos}
        total_weight = sum(weight.values()) or 1.0
        names = {p.path: p.name or p.path for p in photos}
        done = 0
        gained = 0.0
        failures: list[tuple[str, str]] = []
        trashed: list[str] = []

        def emit(current: str = "") -> None:
            report(Progress(done, total, int(gained), int(total_weight), current=current))

        def handle(result: dict, share: float, counts_done: bool, collect: bool) -> None:
            nonlocal done, gained
            uid = result.get("uid", "")
            if result.get("ok"):
                gained += weight.get(uid, 1.0) * share
                if collect:
                    trashed.append(uid)
            else:
                message = (result.get("error") or {}).get("message") or "unknown error"
                failures.append((names.get(uid, uid), message))
            if counts_done:
                done += 1
            emit(names.get(uid, uid))

        cancelled = False
        try:
            for chunk in _chunks(photos, CHUNK):
                self._node_command("trash", [f"/photos/{p.path}" for p in chunk], cancel,
                                   lambda r: handle(r, 0.5 if permanent else 1.0, not permanent, True))
            if permanent and trashed:
                report(Progress(done, total, int(gained), int(total_weight), stage="empty_trash"))
                nodes = self._trash_nodes(cancel)
                by_uid = {n.get("uid"): n for n in nodes}
                counts = Counter(self._node_name(n) for n in nodes)
                targets: list[str] = []
                for uid in trashed:
                    node = by_uid.get(uid)
                    if node is None:
                        done += 1
                        gained += weight.get(uid, 1.0) * 0.5
                        continue
                    name = self._node_name(node)
                    if counts[name] > 1:
                        failures.append((name, "Duplicate name in the Photos trash; skipped to avoid "
                                               "deleting a different item. Delete it manually."))
                        done += 1
                        gained += weight.get(uid, 1.0) * 0.5
                        emit(name)
                        continue
                    targets.append("/photos-trash/" + name.replace("/", "\\/"))
                for chunk in _chunks(targets, CHUNK):
                    self._node_command("delete", chunk, cancel, lambda r: handle(r, 0.5, True, False))
        except Cancelled:
            cancelled = True
        emit()
        return BatchResult("permanent" if permanent else "trash", total, done,
                           int(total_weight), int(gained), failures, cancelled)

    # ----------------------------------------------------------------- find binary by architecture
    @staticmethod
    def _cli_filenames() -> list[str]:
        machine = platform.machine().lower()
        arch = {"amd64": "x64", "x86_64": "x64", "arm64": "arm64", "aarch64": "arm64"}.get(machine, machine)
        system = {"win32": "windows", "linux": "linux", "darwin": "darwin"}.get(sys.platform, sys.platform)
        ext = ".exe" if os.name == "nt" else ""
        return [f"proton-drive-{system}-{arch}{ext}", f"proton-drive{ext}"]

    def _find_exe(self) -> Path:
        env = os.environ.get("PROTON_DRIVE_CLI")
        if env and Path(env).is_file():
            return Path(env)
        roots = [
            Path(getattr(sys, "_MEIPASS", Path.cwd())),
            Path(sys.executable).resolve().parent,
            Path(sys.executable).resolve().parent / "_internal",
            Path(__file__).resolve().parents[3] / "vendor" / "proton-drive",
        ]
        for name in self._cli_filenames():
            for root in roots:
                if (root / name).is_file():
                    return root / name
            found = shutil.which(name)
            if found:
                return Path(found)
        raise AppError("error.cli_missing", debug=f"Searched {roots} for {self._cli_filenames()}")