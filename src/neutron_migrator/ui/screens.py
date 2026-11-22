from __future__ import annotations

import shutil
from pathlib import Path

from PySide6.QtCore import Qt, QTimer, QUrl
from PySide6.QtGui import QDesktopServices, QGuiApplication
from PySide6.QtWidgets import (QButtonGroup, QCheckBox, QComboBox, QFileDialog, QHBoxLayout,
                               QLabel, QLineEdit, QProgressBar, QRadioButton, QVBoxLayout,
                               QWidget)

from ..errors import AppError, Cancelled
from ..security import redact
from ..workers import run
from .widgets import (ErrorDialog, button, card, format_eta, format_size, label, open_folder,
                      show_error)


class Screen(QWidget):
    def __init__(self, ctx):
        super().__init__()
        self.ctx = ctx
        self.i18n = ctx.i18n
        self.worker = None
        self.root = QVBoxLayout(self)
        self.root.setContentsMargins(28, 20, 28, 24)
        self.root.setSpacing(16)

    def fail(self, exc: BaseException) -> None:
        if isinstance(exc, Cancelled):
            return
        show_error(self, self.ctx, exc)


# --------------------------------------------------------------------- login
class LoginScreen(Screen):
    def __init__(self, ctx):
        super().__init__(ctx)
        frame, lay = card()
        lay.addWidget(label(self.i18n, "login.title", "h1"))
        lay.addWidget(label(self.i18n, "login.subtitle", "muted", wrap=True))
        lay.addWidget(label(self.i18n, "login.third_party", "warning", wrap=True))

        self.keep = QCheckBox()
        self.keep.setChecked(ctx.settings.keep_session)
        self.i18n.bind(self.keep, "login.keep")

        self.status = QLabel()
        self.status.setObjectName("muted")
        self.status.setWordWrap(True)

        self.url_hint = label(self.i18n, "login.url_hint", "muted", wrap=True)
        self.url = QLineEdit()
        self.url.setReadOnly(True)
        self.open_btn = button(self.i18n, "login.open_browser")
        self.open_btn.clicked.connect(self._open_browser)
        self.copy_btn = button(self.i18n, "login.copy_link")
        self.copy_btn.clicked.connect(self._copy_link)
        for widget in (self.url_hint, self.url, self.open_btn, self.copy_btn):
            widget.setVisible(False)

        self.signin = button(self.i18n, "login.sign_in_browser", "primary")
        self.signin.clicked.connect(self.sign_in)
        self.resume = button(self.i18n, "login.resume")
        self.resume.clicked.connect(self.resume_session)
        self.resume.setVisible(False)
        self.cancel_btn = button(self.i18n, "common.cancel")
        self.cancel_btn.clicked.connect(self._cancel)
        self.cancel_btn.setVisible(False)

        for widget in (self.keep, self.status, self.url_hint, self.url):
            lay.addWidget(widget)
        link_row = QHBoxLayout()
        link_row.addWidget(self.open_btn)
        link_row.addWidget(self.copy_btn)
        link_row.addStretch(1)
        lay.addLayout(link_row)
        buttons = QHBoxLayout()
        buttons.addWidget(self.cancel_btn)
        buttons.addWidget(self.resume)
        buttons.addStretch(1)
        buttons.addWidget(self.signin)
        lay.addLayout(buttons)
        self.root.addWidget(frame)
        self.root.addStretch(1)
        self.ai_note = label(self.i18n, "about.ai_assisted", "fineprint", wrap=True)
        self.ai_note.setAlignment(Qt.AlignmentFlag.AlignHCenter)
        self.root.addWidget(self.ai_note)

        self.i18n.bind(self.status, "login.starting")
        self.signin.setEnabled(False)
        self.keep.setEnabled(False)
        self.worker = run(self, lambda c, r: self._startup(), self._ready, self._start_failed)

    # -- engine bootstrap (off the UI thread)
    def _startup(self):
        self.ctx.engine.start()
        saved = self.ctx.engine.has_saved_session()
        account = self.ctx.engine.account_name() if saved else ""
        return saved, account

    def _ready(self, result) -> None:
        saved, account = result
        self.signin.setEnabled(True)
        self.keep.setEnabled(True)
        self.i18n.unbind(self.status)
        self.status.clear()
        if saved:
            self.ctx.account = account
            self.resume.setVisible(True)

    def _start_failed(self, exc) -> None:
        self.keep.setEnabled(True)
        self.signin.setEnabled(True)
        self.fail(exc)
        self.i18n.bind(self.status, "error.cli_start")

    # -- sign-in
    def _launch(self, fn) -> None:
        self.signin.setEnabled(False)
        self.resume.setEnabled(False)
        self.cancel_btn.setVisible(True)
        self.i18n.bind(self.status, "login.waiting_browser")
        self.worker = run(self, fn, self._done, self._auth_failed, self._on_progress)

    def sign_in(self) -> None:
        engine = self.ctx.engine
        self._launch(lambda c, r: (engine.start(), engine.login_via_browser(c, r),
                                   engine.account_name())[2])

    def resume_session(self) -> None:
        engine = self.ctx.engine
        self._launch(lambda c, r: (engine.start(), engine.resume(), engine.account_name())[2])

    def _cancel(self) -> None:
        if self.worker:
            self.worker.cancel()

    def _on_progress(self, payload) -> None:
        if isinstance(payload, dict) and payload.get("signInUrl"):
            self.url.setText(payload["signInUrl"])
            for widget in (self.url_hint, self.url, self.open_btn, self.copy_btn):
                widget.setVisible(True)

    def _open_browser(self) -> None:
        QDesktopServices.openUrl(QUrl(self.url.text()))

    def _copy_link(self) -> None:
        QGuiApplication.clipboard().setText(self.url.text())
        self.i18n.bind(self.copy_btn, "common.copied")
        QTimer.singleShot(1500, self._restore_copy_label)

    def _restore_copy_label(self) -> None:
        self.i18n.bind(self.copy_btn, "login.copy_link")

    def _done(self, account) -> None:
        self.ctx.account = account or ""
        self.ctx.settings.keep_session = self.keep.isChecked()
        self.ctx.settings.save()
        self.ctx.go("home")

    def _auth_failed(self, exc) -> None:
        self.signin.setEnabled(True)
        self.resume.setEnabled(True)
        self.cancel_btn.setVisible(False)
        self.i18n.unbind(self.status)
        self.status.clear()
        if isinstance(exc, Cancelled):
            return
        if isinstance(exc, AppError) and exc.key == "error.not_signed_in":
            self.resume.setVisible(False)
        self.fail(exc)


# ---------------------------------------------------------------------- home
class HomeScreen(Screen):
    def __init__(self, ctx):
        super().__init__(ctx)
        self.root.addWidget(label(self.i18n, "home.title", "h1"))
        account = ctx.account or self.i18n.t("home.account_fallback")
        self.root.addWidget(label(self.i18n, "home.account", "muted", account=account))
        for kind, title, desc in (("download", "home.download_title", "home.download_desc"),
                                  ("delete", "home.delete_title", "home.delete_desc")):
            frame, lay = card()
            lay.addWidget(label(self.i18n, title, "h2"))
            lay.addWidget(label(self.i18n, desc, "muted", wrap=True))
            start = button(self.i18n, "home.start", "danger" if kind == "delete" else "primary")
            start.clicked.connect(lambda _=False, k=kind: ctx.go("action", kind=k))
            buttons = QHBoxLayout()
            buttons.addStretch(1)
            buttons.addWidget(start)
            lay.addLayout(buttons)
            self.root.addWidget(frame)
        self.root.addStretch(1)
        self.status = label(self.i18n, "home.signing_out", "muted")
        self.status.setVisible(False)
        self.signout = button(self.i18n, "home.sign_out")
        self.signout.clicked.connect(self._sign_out)
        footer = QHBoxLayout()
        footer.addWidget(self.status)
        footer.addStretch(1)
        footer.addWidget(self.signout)
        self.root.addLayout(footer)

    def _sign_out(self) -> None:
        self.signout.setEnabled(False)
        self.status.setVisible(True)
        self.worker = run(self, lambda c, r: self.ctx.engine.sign_out(),
                          self._signed_out, self._sign_out_failed)

    def _signed_out(self, _result) -> None:
        self.ctx.account = ""
        self.ctx.settings.keep_session = False
        self.ctx.settings.save()
        self.ctx.go("login")

    def _sign_out_failed(self, exc) -> None:
        self.signout.setEnabled(True)
        self.status.setVisible(False)
        self.fail(exc)


# -------------------------------------------------------------------- action
class ActionScreen(Screen):
    def __init__(self, ctx, kind: str):
        super().__init__(ctx)
        self.kind = kind
        self.scan_result = None
        self._pending_home = False
        self._rescan_pending = False
        self._scan_notes = ""
        self._elapsed = 0
        self.root.addWidget(label(self.i18n, f"action.{kind}_title", "h1"))

        options, lay = card()
        scope_row = QHBoxLayout()
        scope_row.addWidget(label(self.i18n, "action.scope"))
        self.scope = QComboBox()
        self.scope.setMinimumWidth(260)
        self.scope.currentIndexChanged.connect(self._scope_changed)
        scope_row.addWidget(self.scope, 1)
        self.rescan = button(self.i18n, "action.rescan")
        self.rescan.clicked.connect(self.start_scan)
        scope_row.addWidget(self.rescan)
        lay.addLayout(scope_row)

        self.videos = QCheckBox()
        self.i18n.bind(self.videos, "action.include_videos")
        self.videos.setChecked(getattr(ctx.settings, "include_videos", False))
        self.videos.toggled.connect(self._videos_changed)
        lay.addWidget(self.videos)

        self.destination = QLineEdit()
        self.destination.setReadOnly(True)
        self.destination.setText(ctx.settings.last_destination)
        self.i18n.bind(self.destination, "action.destination", "placeholderText")
        self.browse = button(self.i18n, "common.browse")
        self.browse.clicked.connect(self._choose_folder)
        self.dest_hint = label(self.i18n, "action.destination_hint", "muted", wrap=True)
        self.dest_row = QHBoxLayout()
        self.dest_row.addWidget(self.destination, 1)
        self.dest_row.addWidget(self.browse)

        self.mode_group = QButtonGroup(self)
        self.trash = QRadioButton()
        self.permanent = QRadioButton()
        self.i18n.bind(self.trash, "action.mode_trash")
        self.i18n.bind(self.permanent, "action.mode_permanent")
        self.mode_group.addButton(self.trash, 0)
        self.mode_group.addButton(self.permanent, 1)
        (self.permanent if ctx.settings.delete_mode == "permanent" else self.trash).setChecked(True)
        self.mode_group.buttonClicked.connect(self._mode_changed)
        self.perm_warning = label(self.i18n, "action.permanent_warning", "warning", wrap=True)
        self.ack = QCheckBox()
        self.i18n.bind(self.ack, "action.permanent_ack")
        self.ack.toggled.connect(self._update_confirm)

        if kind == "download":
            lay.addLayout(self.dest_row)
            lay.addWidget(self.dest_hint)
            self.mode_widgets = ()
        else:
            lay.addWidget(label(self.i18n, "action.delete_mode"))
            lay.addWidget(self.trash)
            lay.addWidget(self.permanent)
            lay.addWidget(self.perm_warning)
            lay.addWidget(self.ack)
            self.mode_widgets = (self.perm_warning, self.ack)
        self.root.addWidget(options)

        summary, slay = card()
        self.summary = QLabel()
        self.summary.setObjectName("h2")
        self.summary.setWordWrap(True)
        self.scan_bar = QProgressBar()
        self.scan_bar.setRange(0, 0)
        self.scan_bar.setTextVisible(False)
        self.warning = QLabel()
        self.warning.setObjectName("warning")
        self.warning.setWordWrap(True)
        self.warning.setVisible(False)
        slay.addWidget(self.summary)
        slay.addWidget(self.scan_bar)
        slay.addWidget(self.warning)
        self.root.addWidget(summary)
        self.root.addStretch(1)

        self.back = button(self.i18n, "common.back")
        self.back.clicked.connect(self._go_back)
        self.confirm = button(self.i18n, "common.confirm",
                              "danger" if kind == "delete" else "primary")
        self.confirm.clicked.connect(self._confirm)
        self.confirm.setEnabled(False)
        footer = QHBoxLayout()
        footer.addWidget(self.back)
        footer.addStretch(1)
        footer.addWidget(self.confirm)
        self.root.addLayout(footer)

        self._mode_changed()  # every widget exists at this point

        self._timer = QTimer(self)
        self._timer.setInterval(1000)
        self._timer.timeout.connect(self._tick)
        self._load_scopes()

    # -- setup
    def _load_scopes(self) -> None:
        self.i18n.bind(self.summary, "action.loading")
        self.scan_bar.setVisible(True)
        self.worker = run(self, lambda c, r: self.ctx.engine.root_folders(),
                          self._scopes_ready, self._scan_failed)

    def _scopes_ready(self, folders: list[str]) -> None:
        self.scope.blockSignals(True)
        self.scope.clear()
        self.scope.addItem(self.i18n.t("action.scope_all"), "")
        for folder in folders:
            self.scope.addItem(folder, folder)
        wanted = self.ctx.settings.scope
        if wanted and wanted not in folders:
            wanted = ""
        if not wanted:
            wanted = self.ctx.engine.preferred_scope(folders)
        self.scope.setCurrentIndex(max(0, self.scope.findData(wanted)))
        self.scope.blockSignals(False)
        self.ctx.settings.scope = self.scope.currentData() or ""
        self.start_scan()

    def _scope_changed(self) -> None:
        self.ctx.settings.scope = self.scope.currentData() or ""
        self.ctx.settings.save()
        self.start_scan()

    def _videos_changed(self) -> None:
        self.ctx.settings.include_videos = self.videos.isChecked()
        self.ctx.settings.save()
        self.start_scan()

    def _mode_changed(self, *_args) -> None:
        permanent = self.permanent.isChecked()
        self.ctx.settings.delete_mode = "permanent" if permanent else "trash"
        self.ctx.settings.save()
        for widget in self.mode_widgets:
            widget.setVisible(permanent)
        if not permanent:
            self.ack.setChecked(False)
        self._update_confirm()

    def _choose_folder(self) -> None:
        start = self.destination.text() or str(Path.home())
        chosen = QFileDialog.getExistingDirectory(self, self.i18n.t("action.choose_folder"), start)
        if chosen:
            self.destination.setText(chosen)
            self.ctx.settings.last_destination = chosen
            self.ctx.settings.save()
        self._update_confirm()

    # -- scan
    def start_scan(self) -> None:
        if self.worker is not None and self.worker.isRunning():
            self._rescan_pending = True
            self.worker.cancel()
            return
        self._rescan_pending = False
        self.scan_result = None
        self._scan_notes = ""
        self.confirm.setEnabled(False)
        self.warning.setVisible(False)
        self.scan_bar.setVisible(True)
        self._elapsed = 0
        self._timer.start()
        self.i18n.bind(self.summary, "action.scanning", seconds=0)
        scope = self.scope.currentData() or ""
        include_videos = self.videos.isChecked()
        self.worker = run(self, lambda c, r: self.ctx.engine.scan(scope, c, include_videos),
                          self._scan_done, self._scan_failed)

    def _tick(self) -> None:
        self._elapsed += 1
        self.i18n.bind(self.summary, "action.scanning", seconds=self._elapsed)

    def _scan_done(self, result) -> None:
        self._timer.stop()
        self.scan_bar.setVisible(False)
        if self._pending_home:
            self.ctx.go("home")
            return
        if self._rescan_pending:
            self._rescan_pending = False
            self.start_scan()
            return
        self.scan_result = result
        if result.count == 0:
            self.i18n.bind(self.summary, "action.found_none")
        else:
            self.i18n.bind(self.summary, "action.found", count=result.count,
                           size=format_size(self.i18n, result.total_bytes))
        notes = []
        unknown = getattr(result, "unknown_sizes", 0)
        videos = getattr(result, "videos", 0)
        if unknown:
            notes.append(self.i18n.t("action.unknown_sizes", count=unknown))
        if videos and not self.videos.isChecked():
            notes.append(self.i18n.t("action.videos_skipped", count=videos,
                                     size=format_size(self.i18n, getattr(result, "video_bytes", 0))))
        self._scan_notes = "\n".join(notes)
        self._update_confirm()

    def _scan_failed(self, exc) -> None:
        self._timer.stop()
        self.scan_bar.setVisible(False)
        if self._pending_home:
            self.ctx.go("home")
            return
        if self._rescan_pending:
            self._rescan_pending = False
            self.start_scan()
            return
        self.i18n.bind(self.summary, "action.found_none")
        if not isinstance(exc, Cancelled):
            self.fail(exc)

    # -- confirm
    def _update_confirm(self) -> None:
        result = self.scan_result
        ready = bool(result and result.count)
        messages = [self._scan_notes] if self._scan_notes else []
        if ready and self.kind == "download":
            dest = self.destination.text()
            if not dest or not Path(dest).is_dir():
                ready = False
            else:
                free = shutil.disk_usage(dest).free
                if free < result.total_bytes * 1.02:
                    ready = False
                    messages.append(self.i18n.t(
                        "action.free_space",
                        free=format_size(self.i18n, free),
                        needed=format_size(self.i18n, result.total_bytes)))
        if ready and self.kind == "delete" and self.permanent.isChecked():
            ready = self.ack.isChecked()
        self.confirm.setEnabled(ready)
        self.warning.setText("\n".join(m for m in messages if m))
        self.warning.setVisible(bool(messages))
        if result and result.count:
            key = ("action.confirm_download" if self.kind == "download"
                   else "action.confirm_permanent" if self.permanent.isChecked()
                   else "action.confirm_trash")
            self.i18n.bind(self.confirm, key, count=result.count)
        else:
            self.i18n.bind(self.confirm, "common.confirm")

    def _confirm(self) -> None:
        if not self.scan_result:
            return
        mode = "permanent" if self.kind == "delete" and self.permanent.isChecked() else "trash"
        self.ctx.go("progress", kind=self.kind, photos=self.scan_result.photos,
                    destination=self.destination.text(), mode=mode)

    def _go_back(self) -> None:
        if self.worker and self.worker.isRunning():
            self._pending_home = True
            self.worker.cancel()
            self.back.setEnabled(False)
            return
        self.ctx.go("home")


# ------------------------------------------------------------------ progress
class ProgressScreen(Screen):
    def __init__(self, ctx, kind: str, photos, destination: str, mode: str):
        super().__init__(ctx)
        self.kind, self.photos, self.destination, self.mode = kind, photos, destination, mode
        stage = "download" if kind == "download" else mode
        frame, lay = card()
        self.title = label(self.i18n, f"progress.{stage}", "h1")
        lay.addWidget(self.title)
        self.bar = QProgressBar()
        self.bar.setRange(0, 1000)
        self.bar.setValue(0)
        lay.addWidget(self.bar)
        self.stats = QLabel()
        self.stats.setObjectName("muted")
        self.stats.setWordWrap(True)
        lay.addWidget(self.stats)
        self.current = QLabel()
        self.current.setObjectName("muted")
        self.current.setWordWrap(True)
        lay.addWidget(self.current)
        self.root.addWidget(frame)
        self.root.addStretch(1)
        self.cancel_btn = button(self.i18n, "common.cancel")
        self.cancel_btn.clicked.connect(self._cancel)
        footer = QHBoxLayout()
        footer.addStretch(1)
        footer.addWidget(self.cancel_btn)
        self.root.addLayout(footer)
        QTimer.singleShot(0, self._start)

    def _start(self) -> None:
        concurrency = self.ctx.settings.concurrency
        engine = self.ctx.engine
        if self.kind == "download":
            fn = lambda c, r: engine.download(self.photos, Path(self.destination), c, r, concurrency)
        else:
            fn = lambda c, r: engine.delete(self.photos, self.mode, c, r, concurrency)
        self.worker = run(self, fn, self._done, self._failed, self._progress)

    def _progress(self, p) -> None:
        if p.stage == "empty_trash":
            self.i18n.bind(self.title, "progress.emptying")
        if p.stage == "waiting":
            self.i18n.bind(self.current, "progress.retrying")
            return
        if p.total_bytes:
            ratio = p.done_bytes / p.total_bytes
        elif p.total_files:
            ratio = p.done_files / p.total_files
        else:
            ratio = 0.0
        self.bar.setRange(0, 1000)
        self.bar.setValue(int(min(1.0, ratio) * 1000))
        if self.kind == "download":
            eta = format_eta(p.eta) or self.i18n.t("progress.eta_unknown")
            self.stats.setText(self.i18n.t(
                "progress.stats", done=p.done_files, total=p.total_files,
                done_size=format_size(self.i18n, p.done_bytes),
                total_size=format_size(self.i18n, p.total_bytes),
                speed=format_size(self.i18n, p.speed), eta=eta))
        else:
            self.stats.setText(self.i18n.t("progress.files", done=p.done_files, total=p.total_files))
        self.i18n.unbind(self.current)
        self.current.setText(self.i18n.t("progress.current", path=p.current) if p.current else "")

    def _cancel(self) -> None:
        self.cancel_btn.setEnabled(False)
        self.i18n.bind(self.current, "progress.cancelling")
        if self.worker:
            self.worker.cancel()

    def _done(self, result) -> None:
        self.ctx.go("result", result=result, destination=self.destination)

    def _failed(self, exc) -> None:
        self.fail(exc)
        expired = isinstance(exc, AppError) and exc.key == "error.session_expired"
        self.ctx.go("login" if expired else "home")


# -------------------------------------------------------------------- result
class ResultScreen(Screen):
    def __init__(self, ctx, result, destination: str):
        super().__init__(ctx)
        self.result, self.destination = result, destination
        frame, lay = card()
        headline = QLabel()
        headline.setObjectName("h1")
        headline.setWordWrap(True)
        size = format_size(self.i18n, result.done_bytes)
        if result.cancelled:
            headline.setText(self.i18n.t("result.cancelled", count=result.done, total=result.total))
        elif result.failures:
            headline.setText(self.i18n.t("result.partial", count=result.done,
                                         total=result.total, failed=len(result.failures)))
        else:
            headline.setText(self.i18n.t(f"result.{result.kind}_ok", count=result.done, size=size))
        lay.addWidget(headline)
        if result.kind == "download" and destination:
            lay.addWidget(label(self.i18n, "result.destination", "muted", wrap=True, path=destination))
        if result.warning_key:
            warn = QLabel(self.i18n.t(result.warning_key))
            warn.setObjectName("warning")
            warn.setWordWrap(True)
            lay.addWidget(warn)
        if result.failures:
            lay.addWidget(label(self.i18n, "result.failures", "warning", wrap=True,
                                failed=len(result.failures)))
        self.root.addWidget(frame)
        self.root.addStretch(1)

        back = button(self.i18n, "result.back", "primary")
        back.clicked.connect(lambda: ctx.go("home"))
        footer = QHBoxLayout()
        if result.failures or result.warning_debug:
            details = button(self.i18n, "result.details")
            details.clicked.connect(self._details)
            footer.addWidget(details)
        if result.kind == "download" and destination:
            open_btn = button(self.i18n, "result.open_folder")
            open_btn.clicked.connect(lambda: open_folder(destination))
            footer.addWidget(open_btn)
        retry = getattr(result, "retry_photos", [])
        if retry and result.kind == "download":
            retry_btn = button(self.i18n, "result.retry_failed", count=len(retry))
            retry_btn.clicked.connect(lambda: ctx.go("progress", kind="download", photos=retry,
                                                     destination=destination, mode="trash"))
            footer.addWidget(retry_btn)
        footer.addStretch(1)
        footer.addWidget(back)
        self.root.addLayout(footer)

    def _details(self) -> None:
        lines = [f"Operation: {self.result.kind}",
                 f"Processed: {self.result.done}/{self.result.total}",
                 f"Cancelled: {self.result.cancelled}", ""]
        if self.result.warning_debug:
            lines += ["Warning:", self.result.warning_debug, ""]
        lines += ["Failed items:"] + [f"- {path}\n  {error}" for path, error in self.result.failures]
        ErrorDialog(self, self.ctx,
                    self.ctx.i18n.t("result.failures", failed=len(self.result.failures)),
                    redact("\n".join(lines)), title_key="common.debug").exec()