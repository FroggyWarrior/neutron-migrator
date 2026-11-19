"""Engine adapter: drives Proton's own auth/crypto stack (go-proton-api + gopenpgp)
through rclone's protondrive backend, exposed over a loopback-only RC API.

Swap this file for the official Proton Drive SDK when it is available: the rest of
the app only depends on the public methods and the dataclasses in base.py.
"""
from __future__ import annotations

import json
import os
import shutil
import socket
import subprocess
import sys
import threading
import time
from collections import deque
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import requests

from .. import security
from ..config import MIN_RCLONE
from ..errors import AppError, Cancelled, Challenge, RcError
from .base import PHOTO_FOLDER_HINTS, BatchResult, Photo, Progress, ScanResult, is_photo
from .proton_api import ProtonApi

REMOTE = "neutron"
FS = f"{REMOTE}:"


class RcloneEngine:
    def __init__(self, workdir: Path):
        self.workdir = workdir
        self.config_file = workdir / "rclone.conf"
        self.exe: Path | None = None
        self.version = "unknown"
        self.can_persist = False
        self.signed_in = False
        self._proc: subprocess.Popen | None = None
        self._port = 0
        self._auth: tuple[str, str] = ("", "")
        self._log: deque[str] = deque(maxlen=600)
        self._jobs: set[int] = set()
        self._lock = threading.Lock()

    # ---------------------------------------------------------------- lifecycle
    def _find_exe(self) -> Path:
        name = "rclone.exe" if os.name == "nt" else "rclone"
        roots = [Path(os.environ.get("RCLONE_EXE", ""))] if os.environ.get("RCLONE_EXE") else []
        roots += [
            Path(sys.executable).resolve().parent / name,
            Path(getattr(sys, "_MEIPASS", Path.cwd())) / name,
            Path(__file__).resolve().parents[3] / "vendor" / "rclone" / name,
        ]
        for candidate in roots:
            if candidate.is_file():
                return candidate
        found = shutil.which("rclone")
        if found:
            return Path(found)
        raise AppError("error.rclone_missing", debug=f"Searched: {[str(p) for p in roots]} and PATH")

    def start(self) -> None:
        if self._proc and self._proc.poll() is None:
            return
        self.exe = self._find_exe()
        key, self.can_persist = security.config_key()
        with socket.socket() as s:
            s.bind(("127.0.0.1", 0))
            self._port = s.getsockname()[1]
        password = security.secrets.token_urlsafe(32) if hasattr(security, "secrets") else __import__("secrets").token_urlsafe(32)
        security.remember(password)
        self._auth = ("neutron", password)
        env = dict(os.environ)
        env.update({
            "RCLONE_CONFIG": str(self.config_file),
            "RCLONE_CONFIG_PASS": key,
            "RCLONE_RC_ADDR": f"127.0.0.1:{self._port}",
            "RCLONE_RC_USER": self._auth[0],
            "RCLONE_RC_PASS": self._auth[1],
        })
        args = [str(self.exe), "rcd", "--log-level", "NOTICE", "--contimeout", "30s",
                "--timeout", "10m", "--low-level-retries", "5", "--retries", "1", "--stats", "1s"]
        try:
            self._proc = subprocess.Popen(  # noqa: S603
                args, env=env, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE,
                text=True, encoding="utf-8", errors="replace",
                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
            )
        except OSError as exc:
            raise AppError("error.rclone_start", debug=f"{args}\n{exc!r}") from exc
        threading.Thread(target=self._pump_log, daemon=True).start()
        deadline = time.monotonic() + 25
        while time.monotonic() < deadline:
            try:
                info = self._rc("core/version", timeout=3)
                self.version = info.get("version", "unknown")
                parts = tuple(info.get("decomposed") or [])[:3]
                if parts and parts < MIN_RCLONE:
                    raise AppError("error.unsupported_version", version=self.version,
                                   debug=f"rclone {self.version} at {self.exe}")
                security.restrict(self.config_file)
                return
            except AppError:
                raise
            except Exception:
                if self._proc.poll() is not None:
                    break
                time.sleep(0.25)
        raise AppError("error.rclone_start", debug=self.log_tail(80))

    def _pump_log(self) -> None:
        if not self._proc or not self._proc.stderr:
            return
        for line in self._proc.stderr:
            self._log.append(line.rstrip())

    def log_tail(self, lines: int = 60) -> str:
        return "\n".join(list(self._log)[-lines:])

    def shutdown(self, keep: bool) -> None:
        if self._proc and self._proc.poll() is None:
            if not keep and self.signed_in:
                try:
                    self._api().logout()
                except Exception:
                    pass
            try:
                self._rc("core/quit", timeout=4)
            except Exception:
                pass
            try:
                self._proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                self._proc.terminate()
                try:
                    self._proc.wait(timeout=3)
                except subprocess.TimeoutExpired:
                    self._proc.kill()
        self._proc = None
        self.signed_in = False
        if not keep:
            security.wipe(self.config_file)

    # ------------------------------------------------------------------ RC glue
    def _rc(self, endpoint: str, payload: dict | None = None, timeout: float = 120) -> dict:
        url = f"http://127.0.0.1:{self._port}/{endpoint}"
        try:
            r = requests.post(url, json=payload or {}, auth=self._auth, timeout=timeout)
        except requests.RequestException as exc:
            raise RcError(endpoint, 0, repr(exc)) from exc
        if r.status_code != 200:
            raise RcError(endpoint, r.status_code, r.text)
        try:
            return r.json() if r.text.strip() else {}
        except ValueError:
            return {}

    def _job(self, endpoint: str, payload: dict, cancel: threading.Event | None = None, poll: float = 0.4) -> dict:
        jobid = self._rc(endpoint, {**payload, "_async": True}).get("jobid")
        if jobid is None:
            raise AppError("error.generic", message="engine returned no job id", debug=f"{endpoint} {payload}")
        with self._lock:
            self._jobs.add(jobid)
        try:
            while True:
                if cancel is not None and cancel.is_set():
                    try:
                        self._rc("job/stop", {"jobid": jobid}, timeout=10)
                    except Exception:
                        pass
                    raise Cancelled()
                status = self._rc("job/status", {"jobid": jobid}, timeout=30)
                if status.get("finished"):
                    if not status.get("success"):
                        raise RcError(endpoint, 500, json.dumps({"error": status.get("error", "unknown")}))
                    return status.get("output") or {}
                time.sleep(poll)
        finally:
            with self._lock:
                self._jobs.discard(jobid)

    def _obscure(self, plaintext: str) -> str:
        security.remember(plaintext)
        result = self._rc("core/obscure", {"clear": plaintext})
        for key, value in result.items():
            if key.lower() == "obscured" and isinstance(value, str) and value:
                security.remember(value)
                return value
        raise AppError(
            "error.generic",
            message="engine did not return an obscured password",
            debug=f"core/obscure response keys: {list(result)}",
        )

    def _option_names(self) -> set[str]:
        for provider in self._rc("config/providers").get("providers", []):
            if provider.get("Name") == "protondrive":
                return {o.get("Name", "") for o in provider.get("Options", [])}
        return set()

    # --------------------------------------------------------------------- auth
    def login(self, username: str, password: str, totp: str | None = None,
              mailbox_password: str | None = None, keep: bool = False) -> None:
        security.remember(password)
        security.remember(totp)
        security.remember(mailbox_password)
        try:
            self._rc("config/delete", {"name": REMOTE}, timeout=15)
        except Exception:
            pass
        names = self._option_names()
        params = {"username": username, "password": self._obscure(password)}
        if totp:
            otp_key = next((n for n in ("2fa", "otp_code", "otp") if n in names), "2fa")
            params[otp_key] = totp
        if mailbox_password:
            params["mailbox_password"] = self._obscure(mailbox_password)
        try:
            result = self._rc("config/create", {
                "name": REMOTE, "type": "protondrive", "parameters": params,
                "opt": {"nonInteractive": True},
            }, timeout=300)
        except RcError as exc:
            raise self._map_auth_error(exc, sent_totp=bool(totp), sent_mailbox=bool(mailbox_password)) from exc
        state, option = result.get("state"), (result.get("option") or {})
        if state:
            name = str(option.get("Name", "")).lower()
            if name in ("2fa", "otp_code", "otp") and not totp:
                raise Challenge("totp")
            if name == "mailbox_password" and not mailbox_password:
                raise Challenge("mailbox")
            raise AppError("error.generic", message=str(option.get("Help") or name or state),
                           debug=json.dumps(result, indent=2)[:3000])
        self._verify()
        self.signed_in = True
        self.can_persist = self.can_persist and keep

    def _verify(self) -> None:
        try:
            self._rc("operations/list", {"fs": FS, "remote": "", "opt": {"noModTime": True, "noMimeType": True}}, timeout=120)
        except RcError as exc:
            raise self._map_auth_error(exc) from exc

    def _map_auth_error(self, exc: RcError, sent_totp: bool = False, sent_mailbox: bool = False) -> Exception:
        raw = exc.body.lower()
        debug = exc.dump() + "\n\nEngine log:\n" + self.log_tail(40)
        if any(k in raw for k in ("captcha", "human verification", "9001")):
            return AppError("error.human_verification", debug=debug)
        if any(k in raw for k in ("fido", "webauthn", "security key", "u2f")):
            return AppError("error.fido_unsupported", debug=debug)
        if "mailbox" in raw and "password" in raw:
            return AppError("error.mailbox_invalid", debug=debug) if sent_mailbox else Challenge("mailbox")
        if any(k in raw for k in ("2fa", "two-factor", "two factor", "totp", "otp")):
            return AppError("error.totp_invalid", debug=debug) if sent_totp else Challenge("totp")
        if any(k in raw for k in ("invalid credentials", "incorrect password", "invalid password",
                                  "username or password", "8002", "password_error")):
            return AppError("error.auth_invalid", debug=debug)
        if any(k in raw for k in ("unauthorized", "401", "session", "refresh token", "expired")):
            return AppError("error.session_expired", debug=debug)
        if any(k in raw for k in ("dial tcp", "no such host", "tls", "timeout", "connection refused", "network")):
            return AppError("error.network", debug=debug)
        return AppError("error.generic", message=exc.message, debug=debug)

    def has_saved_session(self) -> bool:
        try:
            return REMOTE in (self._rc("config/listremotes", timeout=15).get("remotes") or [])
        except Exception:
            return False

    def resume(self) -> None:
        self._verify()
        self.signed_in = True

    def sign_out(self) -> None:
        try:
            self._api().logout()
        except Exception:
            pass
        try:
            self._rc("config/delete", {"name": REMOTE}, timeout=15)
        except Exception:
            pass
        self.signed_in = False
        security.wipe(self.config_file)

    def account_name(self) -> str:
        try:
            return self._rc("config/dump", timeout=15).get(REMOTE, {}).get("username", "")
        except Exception:
            return ""

    # -------------------------------------------------------------------- drive
    def root_folders(self) -> list[str]:
        try:
            out = self._rc("operations/list", {"fs": FS, "remote": "", "opt": {
                "dirsOnly": True, "noModTime": True, "noMimeType": True}}, timeout=120)
        except RcError as exc:
            raise AppError("error.scan_failed", debug=exc.dump()) from exc
        return sorted((i.get("Path") or i.get("Name", "")) for i in out.get("list") or [] if i.get("IsDir"))

    def preferred_scope(self, folders: list[str]) -> str:
        for folder in folders:
            if folder.strip().lower() in PHOTO_FOLDER_HINTS:
                return folder
        return ""

    def scan(self, scope: str, cancel: threading.Event) -> ScanResult:
        try:
            out = self._job("operations/list", {"fs": FS, "remote": scope, "opt": {
                "recurse": True, "filesOnly": True, "noModTime": True, "noMimeType": True}}, cancel=cancel, poll=0.5)
        except Cancelled:
            raise
        except RcError as exc:
            raise AppError("error.scan_failed", debug=exc.dump() + "\n\n" + self.log_tail(40)) from exc
        photos = []
        for item in out.get("list") or []:
            rel = item.get("Path") or item.get("Name", "")
            if not rel or item.get("IsDir") or not is_photo(rel):
                continue
            path = f"{scope}/{rel}" if scope else rel
            photos.append(Photo(path, max(0, int(item.get("Size") or 0))))
        return ScanResult(sorted(photos, key=lambda p: p.path))

    # ------------------------------------------------------------------ actions
    def download(self, photos: list[Photo], destination: Path, cancel, report, concurrency: int) -> BatchResult:
        dest = destination.as_posix()
        return self._batch("download", photos, "operations/copyfile",
                           lambda p: {"srcFs": FS, "srcRemote": p.path, "dstFs": dest, "dstRemote": p.path},
                           cancel, report, concurrency, byte_progress=True)

    def delete(self, photos: list[Photo], mode: str, cancel, report, concurrency: int) -> BatchResult:
        result = self._batch("trash" if mode == "trash" else "permanent", photos, "operations/deletefile",
                             lambda p: {"fs": FS, "remote": p.path}, cancel, report, concurrency, byte_progress=False)
        if mode == "permanent" and not result.cancelled:
            report(Progress(done_files=result.total, total_files=result.total, stage="empty_trash"))
            try:
                self._api().empty_trash()
            except Exception as exc:
                result.warning_key = "error.permanent_failed"
                result.warning_debug = f"{type(exc).__name__}: {exc}\n{getattr(exc, 'debug', '')}"
        return result

    def _batch(self, kind, photos, endpoint, payload_fn, cancel, report, concurrency, byte_progress) -> BatchResult:
        total, total_bytes = len(photos), sum(p.size for p in photos)
        done = done_bytes = 0
        failures: list[tuple[str, str]] = []
        inflight: set[str] = set()
        lock = threading.Lock()
        try:
            self._rc("core/stats-reset", timeout=15)
        except Exception:
            pass

        def handle(photo: Photo) -> None:
            nonlocal done, done_bytes
            if cancel.is_set():
                return
            with lock:
                inflight.add(photo.path)
            try:
                self._job(endpoint, payload_fn(photo), cancel=cancel)
            except Cancelled:
                return
            except Exception as exc:
                with lock:
                    failures.append((photo.path, f"{type(exc).__name__}: {exc}"))
            else:
                with lock:
                    done += 1
                    done_bytes += photo.size
            finally:
                with lock:
                    inflight.discard(photo.path)

        stop = threading.Event()

        def poller() -> None:
            while not stop.wait(0.5):
                stats: dict = {}
                if byte_progress:
                    try:
                        stats = self._rc("core/stats", timeout=10)
                    except Exception:
                        stats = {}
                with lock:
                    transferred = min(int(stats.get("bytes") or 0), total_bytes) if byte_progress else done_bytes
                    shown_bytes = max(done_bytes, transferred)
                    current = next(iter(inflight), "")
                    speed = float(stats.get("speed") or 0)
                remaining = max(0, total_bytes - shown_bytes)
                report(Progress(done, total, shown_bytes, total_bytes, speed,
                                (remaining / speed) if speed > 0 and remaining else None, current))

        thread = threading.Thread(target=poller, daemon=True)
        thread.start()
        try:
            with ThreadPoolExecutor(max_workers=max(1, concurrency)) as pool:
                list(pool.map(handle, photos))
        finally:
            stop.set()
            thread.join(timeout=2)
        report(Progress(done, total, done_bytes, total_bytes))
        return BatchResult(kind, total, done, total_bytes, done_bytes, failures, cancel.is_set())

    # ------------------------------------------------------- direct API session
    def _api(self) -> ProtonApi:
        cfg = self._rc("config/dump", timeout=20).get(REMOTE, {})
        uid = refresh = access = ""
        for key, value in cfg.items():
            k, v = key.lower(), str(value or "")
            security.remember(v)
            if "uid" in k:
                uid = v
            elif "refresh" in k or k in ("client_auth", "auth"):
                refresh = v
            elif "access" in k:
                access = v
        if not uid:
            raise AppError("error.session_expired", debug=f"No UID in engine config keys: {list(cfg)}")
        return ProtonApi(uid, refresh, access)