</p>

<h1 align="center">Neutron Migrator</h1>

<p align="center">
  Download or delete every photo in your Proton Drive — with browser sign-in,
  a confirmation step, and a cancellable progress bar.
</p>

<p align="center">
  <a href="https://github.com/FroggyWarrior/neutron-migrator/releases/latest"><img alt="Release" src="https://img.shields.io/github/v/release/FroggyWarrior/neutron-migrator?sort=semver"></a>
  <a href="https://github.com/FroggyWarrior/neutron-migrator/actions/workflows/build.yml"><img alt="Build" src="https://github.com/FroggyWarrior/neutron-migrator/actions/workflows/build.yml/badge.svg"></a>
  <a href="LICENSE"><img alt="License: GPL-3.0" src="https://img.shields.io/badge/license-GPL--3.0-blue"></a>
  <img alt="Platforms" src="https://img.shields.io/badge/platforms-Windows%20%7C%20Linux%20%7C%20macOS-lightgrey">
</p>

> [!IMPORTANT]
> **Neutron Migrator is an independent, third-party application.** It is not
> affiliated with, endorsed by, or supported by Proton AG. "Proton" and "Proton Drive"
> are trademarks of Proton AG and are used here only to describe interoperability.

---

## Table of contents

- [What it does](#what-it-does)
- [How it works](#how-it-works)
- [Privacy and security](#privacy-and-security)
- [Download and requirements](#download-and-requirements)
- [Usage](#usage)
- [Limitations](#limitations)
- [Build from source](#build-from-source)
- [Packaging and releases](#packaging-and-releases)
- [Configuration and data locations](#configuration-and-data-locations)
- [Troubleshooting](#troubleshooting)
- [Translations and themes](#translations-and-themes)
- [Project layout](#project-layout)
- [Licensing](#licensing)
- [Credits](#credits)

---

## What it does

Neutron Migrator is a desktop app with exactly two jobs:

1. **Download all photos** from your Proton Drive to a folder on your computer.
2. **Delete all photos** from your Proton Drive — either to the trash (recoverable)
   or permanently.

Both actions follow the same safe flow:

```
sign in → scan → review count & size → confirm → progress (cancellable) → summary → back
```

Nothing is downloaded or deleted before you see the totals and press the confirmation
button.

### Features

- **Browser sign-in.** Authentication happens on Proton's website through the official
  Proton Drive CLI, so CAPTCHA, TOTP 2FA, FIDO2 security keys and two-password mode all
  work exactly as in the browser. The app never asks for, sees, or stores your password.
- **Session in the OS keychain** (Windows Credential Manager, macOS Keychain,
  libsecret on Linux). Optional "keep me signed in"; otherwise the session is revoked
  on exit.
- **Dry-run totals**: number of photos and total size before any action.
- **Destination picker** with a free-space check for downloads.
- **Progress bar** with per-file counters, transferred bytes, and a cancel button that
  stops cleanly.
- **Two deletion modes**: move to trash, or permanent deletion of *only* the selected
  photos (items with duplicate names in the Photos trash are skipped and reported).
- **English / Spanish** UI, switchable at runtime; **dark / light / system** theme
  (defaults: English + dark). All strings live in JSON files, so new languages are
  drop-in.
- **Honest errors**: every failure shows a readable message plus a *Show more* panel
  with copyable, secret-redacted debug information (always in English).

## How it works

```
┌──────────────────────────────┐
│  PySide6 (Qt 6) desktop UI   │  screens, i18n JSON, QSS themes
└──────────────┬───────────────┘
               │ worker threads (never blocks the UI)
┌──────────────▼───────────────┐
│  Engine adapter              │  src/neutron_migrator/engine/proton_cli.py
│  (subprocess + --json)       │
└──────────────┬───────────────┘
               │ official, unmodified binary, SHA-512 verified
┌──────────────▼───────────────┐
│  Proton Drive CLI (SDK)      │  encryption, caching, retries, rate limits
└──────────────┬───────────────┘
               │ HTTPS, official Proton endpoints only
        ┌──────▼──────┐
        │ Proton Drive│
        └─────────────┘
```

The engine adapter is the only place that talks to Proton. It shells out to the
**official Proton Drive CLI** (from [ProtonDriveApps/sdk](https://github.com/ProtonDriveApps/sdk))
and parses its `--json` output:

| Step | CLI command |
|---|---|
| Sign in | `auth login --json` (prints the sign-in URL, opens the browser) |
| Session check / account | `filesystem list /my-files --json`, `filesystem info /my-files --json` |
| Scan photos | `photo timeline --json --load-details` |
| Download | `photo download /photos/<uid> … <folder> --json --conflict-strategy rename` |
| Trash | `filesystem trash /photos/<uid> … --json` |
| Permanent delete | `filesystem list /photos-trash --json` → `filesystem delete /photos-trash/<name> … --json` |
| Sign out | `auth logout` |

Operations are batched (40 items per invocation) to stay well below command-line
length limits on every OS. Download progress is measured from the growth of the
destination folder; deletion progress comes from the CLI's streamed JSON results.

Using the official CLI is deliberate: Proton asks third-party developers to integrate
through their SDK rather than raw API calls, so correctness, caching, event handling
and rate-limit behaviour stay aligned with first-party apps.

## Privacy and security

- **No credentials in the app.** Sign-in is delegated to Proton's web login; the CLI
  stores only a session token, in the OS secret store.
- **No telemetry from this app.** Neutron Migrator collects nothing, phones nowhere and
  makes no network calls of its own. The bundled **Proton Drive CLI does send technical
  build telemetry to Proton** — its log shows `Telemetry enabled: build=true, user=false` —
  and it honours the telemetry preference stored in your Proton account. Disable it in
  Proton's account settings if you want it off; this app cannot override it. The only
  other traffic is the CLI talking to official Proton endpoints.
- **Verified engine.** `scripts/fetch_proton_cli.py` downloads the CLI over HTTPS and
  checks it against the SHA-512 checksums published by Proton.
- **Redacted diagnostics.** Passwords, tokens and session identifiers are stripped from
  anything shown or copied from the debug panel.
- **Isolated state.** The CLI's cache, config and logs are redirected into the app's own
  data directory (`PROTON_DRIVE_CACHE_DIR`), with restrictive permissions.
- **Explicit destructive actions.** Permanent deletion requires selecting the mode and
  acknowledging a warning before the confirm button is enabled.

## Download and requirements

Prebuilt binaries are on the [Releases page](https://github.com/FroggyWarrior/neutron-migrator/releases/latest).

| Platform | File | Minimum requirements |
|---|---|---|
| Windows x64 | `NeutronMigrator-windows-x64.zip` | Windows 10 1809+ or Windows 11 |
| Windows ARM64 | `NeutronMigrator-windows-arm64.zip` | Windows 11 on ARM |
| Linux x86_64 | `NeutronMigrator-linux-x86_64.AppImage` · `NeutronMigrator-linux-x64.tar.gz` | glibc 2.34+ (Ubuntu 22.04+, Debian 12+, Fedora 35+, Arch…) |
| Linux ARM64 | `NeutronMigrator-linux-aarch64.AppImage` · `NeutronMigrator-linux-arm64.tar.gz` | glibc 2.39+ (Ubuntu 24.04+, Debian 13+…) |
| macOS Apple Silicon | `NeutronMigrator-macos-arm64.dmg` | macOS 14+ |
| macOS Intel | `NeutronMigrator-macos-x64.dmg` | macOS 14+ |

Additional runtime requirements:

- **Linux:** `libsecret` plus a running Secret Service (GNOME Keyring / KWallet).
  Release binaries bundle the Qt `xcb` libraries; if you run from source on
  Debian/Ubuntu/Mint you also need `libxcb-cursor0`. Never run the app with `sudo`:
  root has no keyring session and sign-in would fail.
- **All platforms:** a default browser for sign-in, and enough free disk space for
  downloads.
- **macOS:** builds are unsigned/un-notarized; the first launch requires
  right-click → **Open**.

Not supported: 32-bit x86, Linux i686 / RISC-V / musl. Qt 6 and the Proton CLI do not
ship builds for those targets.

## Usage

1. **Launch the app.** The engine starts in the background.
2. **Sign in with browser.** A browser window opens on Proton's sign-in page; the URL is
   also shown in the app with *Open browser* / *Copy link* buttons, so you can complete
   it on another device. Complete 2FA/CAPTCHA there. The app detects completion
   automatically.
   - Tick *Keep the session on this device* to stay signed in across restarts
     (stored in the OS keychain). Otherwise you are signed out when the app closes.
3. **Choose an action** on the home screen.
4. **Review the scan.** The app lists your photo timeline and shows
   `N photos · X GiB`. You can rescan at any time.
5. **Configure and confirm.**
   - *Download*: pick the destination folder. Photos are saved directly there; name
     conflicts are renamed automatically so nothing is overwritten. The confirm button
     stays disabled if there is not enough free space.
   - *Delete*: choose **Move to trash** (recoverable from Proton Drive) or
     **Delete permanently**, which additionally requires acknowledging the warning.
6. **Watch the progress.** Cancel at any time; already-processed files stay processed
   and the summary tells you exactly how many.
7. **Summary.** Success, partial result or cancellation, with a *Show details* button
   listing any failed items, *Open folder* for downloads, and **Back** to start over.

If something fails, the error dialog explains it in plain language; **Show more**
reveals the command, exit code and CLI log (in English, secrets redacted) with a copy
button — ideal for bug reports.

## Limitations

- Scope is the **Photos timeline** (`/photos`). Albums, shared-with-me photos and
  regular Drive folders are not browsed by this version.
- Items are filtered by photo extension (JPEG, PNG, HEIC, AVIF, WebP, TIFF, DNG and
  common RAW formats). Videos in the timeline are excluded; the list lives in
  `engine/base.py` (`PHOTO_EXTENSIONS`).
- Permanent deletion addresses trashed items **by name** (a CLI constraint). If two
  items in the Photos trash share a name, that photo is skipped and reported instead of
  risking the wrong deletion.
- Proton Docs/Sheets are not exportable and are ignored by the CLI.
- This is a one-shot migrator, not a sync client: no background sync, no mounting.
- Proton applies the same per-session rate limits to third-party clients as to its own
  apps; very large libraries may take a while.

## Build from source

### Prerequisites

- **Python 3.10 – 3.15** (3.12 recommended; it is what CI uses)
- `git`, and a C toolchain is *not* required (all dependencies ship wheels)
- Linux only: `libsecret` at runtime, `file` + `desktop-file-utils` for AppImage builds

### 1. Set up the environment

```bash
python -m venv .venv
source .venv/bin/activate        # fish: source .venv/bin/activate.fish
                                 # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

### 2. Fetch the Proton Drive CLI engine

```bash
python scripts/fetch_proton_cli.py                 # host platform, checksum verified
python scripts/fetch_proton_cli.py --target linux-arm64 --target windows-x64
```

The binary lands in `vendor/proton-drive/` (git-ignored, ~90 MB per platform).
Available targets: `windows-x64`, `windows-arm64`, `linux-x64`, `linux-arm64`,
`linux-x64-musl`, `linux-arm64-musl`, `darwin-arm64`, `darwin-x64`.

### 3. Run

```bash
python run.py
```

### 4. Build a distributable

```bash
pip install pyinstaller
python scripts/build.py                 # onedir build + archive in dist/
python scripts/build.py --onefile       # single file (slower startup)
python scripts/build.py --no-package    # build only
```

PyInstaller **cannot cross-compile**: build on the OS/architecture you are targeting.

### 5. Platform extras

**Linux — AppImage**

```bash
bash scripts/make_appimage.sh           # produces dist/NeutronMigrator-linux-<arch>.AppImage
```

**Windows — installer** (optional, requires [Inno Setup](https://jrsoftware.org/isinfo.php))

```powershell
iscc packaging\windows\installer_x64.iss      # or installer_arm64.iss
```

**macOS — sign and notarize** (optional, requires an Apple Developer account)

```bash
codesign --deep --force --options runtime --timestamp \
  --entitlements packaging/macos/entitlements.plist \
  --sign "Developer ID Application: YOUR NAME (TEAMID)" "dist/Neutron Migrator.app"
ditto -c -k --keepParent "dist/Neutron Migrator.app" dist/notarize.zip
xcrun notarytool submit dist/notarize.zip --apple-id "$APPLE_ID" \
  --team-id "$TEAM_ID" --password "$APP_PASSWORD" --wait
xcrun stapler staple "dist/Neutron Migrator.app"
hdiutil create -volname "Neutron Migrator" -srcfolder "dist/Neutron Migrator.app" \
  -ov -format UDZO dist/NeutronMigrator-macos-arm64.dmg
```

## Packaging and releases

`.github/workflows/build.yml` builds every supported target on native runners
(Windows x64/ARM64, Linux x64/ARM64, macOS Intel/Apple Silicon) and publishes the
artifacts to a GitHub Release.

```bash
git tag -a v1.0.2 -m "Neutron Migrator 1.0.2"
git push origin v1.0.2
```

Or trigger a build without publishing: **Actions → build → Run workflow**.

The workflow needs `permissions: contents: write` (declared in the file) so the release
job can upload assets.

## Configuration and data locations

Settings are stored in `settings.json` inside the app data directory:

| OS | Directory |
|---|---|
| Linux | `~/.local/share/Neutron Migrator/` |
| macOS | `~/Library/Application Support/Neutron Migrator/` |
| Windows | `%LOCALAPPDATA%\FroggyWarrior\Neutron Migrator\` |

```json
{
  "language": "en",
  "theme": "dark",
  "keep_session": false,
  "concurrency": 4,
  "delete_mode": "trash",
  "scope": "",
  "last_destination": ""
}
```

The `proton-cli/` subdirectory holds the CLI's cache, config and logs. The **session
token is not there** — it lives in the OS secret store under the service
`ch.proton.drive/drive-sdk-cli`, managed by the Proton CLI itself.

To reset everything: sign out from the app (or run `proton-drive auth logout`) and
delete that directory.

## Troubleshooting

| Symptom | Fix |
|---|---|
| "The Proton Drive CLI was not found" | Run `python scripts/fetch_proton_cli.py`, or install `proton-drive` on your `PATH`, or set `PROTON_DRIVE_CLI=/path/to/proton-drive`. |
| Sign-in never completes | Keep the app open until the browser flow finishes; the URL can be opened on another device. |
| Keychain errors on Linux | Install `libsecret` and make sure GNOME Keyring or KWallet is running and unlocked in your session. |
| `Illegal instruction` on an old x86_64 CPU | The bundled CLI needs AVX2. Use a newer machine, or a `x64-baseline` CLI build if Proton publishes one for that version. |
| AppImage does not start | `chmod +x` the file; on systems without FUSE run `./NeutronMigrator-*.AppImage --appimage-extract-and-run`. |
| macOS "cannot be opened" | Unsigned build: right-click → **Open**, or remove quarantine with `xattr -dr com.apple.quarantine "Neutron Migrator.app"`. |
| Wayland `qt.qpa.wayland.textinput` spam | Harmless. Silence with `QT_LOGGING_RULES="qt.qpa.wayland.textinput=false"`. |
| Something else | Open the error dialog → **Show more** → **Copy debug info** and attach it to an issue. |

## Translations and themes

All user-facing strings live in `src/neutron_migrator/assets/i18n/*.json`. To add a
language, copy `en.json`, translate the values (keep the keys and `{placeholders}`),
set `language.name`, and drop the file in that folder — it appears in the language
selector automatically. Missing keys fall back to English. Debug output stays in
English by design.

Themes are a single QSS template (`assets/themes/base.qss`) plus token palettes
(`assets/themes/palettes.json`). `system` follows the desktop colour scheme.

## Project layout

```
neutron-migrator/
├── run.py                     # dev launcher
├── pyproject.toml
├── requirements.txt
├── scripts/
│   ├── fetch_proton_cli.py    # downloads + verifies the official engine
│   ├── build.py               # PyInstaller driver (per-OS/arch)
│   └── make_appimage.sh
├── packaging/
│   ├── icons/                 # icon.png / .ico / .icns
│   ├── linux/                 # .desktop entry
│   ├── macos/                 # entitlements.plist
│   └── windows/               # Inno Setup scripts
├── .github/workflows/build.yml
└── src/neutron_migrator/
    ├── app.py  config.py  errors.py  i18n.py  security.py  theme.py  workers.py
    ├── engine/
    │   ├── base.py            # Photo / ScanResult / Progress / BatchResult
    │   └── proton_cli.py      # official Proton Drive CLI adapter
    ├── ui/
    │   ├── main_window.py  screens.py  widgets.py
    └── assets/
        ├── i18n/en.json  es.json
        └── themes/base.qss  palettes.json
```

## AI use in this project

- **How it was built.** All code, build scripts, CI workflows and documentation were
  written in AI chat sessions (Qwen 3.8-Max / 4-Max). The maintainer
  chose the architecture, integrated the pieces, ran the results and reported real
  failures back for fixing. The application icon was generated by an image model accessed
  through DuckDuckGo AI Chat, which does not disclose the underlying model.

- **What "review" means here.** No independent or line-by-line audit has been performed.
  Validation is functional: the app is executed and its behaviour checked against what it
  claims to do. Bugs found that way were fixed; bugs not found that way may still exist.

- **What is actually tested.** Release binaries are exercised only on **Windows x64 and
  Linux x64**, against a real Proton account — including a ~7,200-item library, full
  downloads and permanent deletion. The remaining targets are built by CI but are **not
  run** by the maintainer.

- **No AI in the product.** No model, no inference, no AI API calls, and no AI features are
  planned. Your password, session tokens and photo contents are never sent to an AI
  service. The app adds no telemetry; the bundled Proton CLI reports its own build
  telemetry to Proton (see [Privacy and security](#privacy-and-security)). Diagnostic logs
  shared during development could contain account identifiers (e-mail address, opaque
  node IDs).

- **Licensing and responsibility.** FroggyWarrior publishes this project under GPL-3.0 and
  is responsible for its releases. Where AI output is not eligible for copyright, it is
  offered for unrestricted reuse. Third-party components keep their own licences — see
  [Licensing](#licensing).

- **Risk.** Deletion is irreversible and this code has not been audited. Try a small
  folder first and keep a backup.

## Licensing

### This project

**Neutron Migrator is free software, licensed under the GNU General Public License
v3.0** — see [LICENSE](LICENSE). You may use, study, modify and redistribute it under
those terms; derivative works must also be GPL-3.0 and include source code.

Copyright © 2026 FroggyWarrior.

### Third-party components

Binaries distributed on the Releases page bundle the following components. Their
licences are included in `THIRD_PARTY_LICENSES/` inside each package.

| Component | Role | Licence |
|---|---|---|
| [Proton Drive CLI / SDK](https://github.com/ProtonDriveApps/sdk) | Engine: authentication, E2EE, Drive & Photos operations | **MIT** (© Proton AG) |
| [Qt 6](https://www.qt.io/) via [PySide6](https://pypi.org/project/PySide6/) | GUI toolkit and Python bindings | **LGPL-3.0** (PySide6 also offers GPL-2.0/GPL-3.0) |
| [platformdirs](https://pypi.org/project/platformdirs/) | Per-OS data directories | **MIT** |
| [requests](https://pypi.org/project/requests/) | HTTPS downloads in the build scripts | **Apache-2.0** |
| [PyInstaller](https://pyinstaller.org/) | Build-time packaging only | **GPL-2.0-or-later with the bootloader exception** (does not impose terms on the built app) |
| Python standard library | Runtime | **PSF License** |

Compliance notes:

- **LGPL (Qt/PySide6):** builds use PyInstaller's *onedir* layout, so the Qt libraries
  remain separate, replaceable files in `_internal/` (or `Contents/Frameworks/` on
  macOS). You can relink or substitute them, as the LGPL requires. The corresponding
  PySide6/Qt source is available from the Qt Project.
- **MIT (Proton Drive CLI):** the binary is redistributed **unmodified**, with Proton's
  copyright and licence text included. It reports its own honest `x-pm-appversion`
  identifier; this project does not spoof Proton first-party clients, does not use
  Proton branding, and only talks to official Proton endpoints.
- **GPL-3.0 (this app):** the complete corresponding source is this repository.

To keep builds compliant, place the licence texts in `THIRD_PARTY_LICENSES/` at the
repo root:

```bash
mkdir -p THIRD_PARTY_LICENSES
curl -L -o THIRD_PARTY_LICENSES/Proton-Drive-SDK-MIT.txt \
  https://raw.githubusercontent.com/ProtonDriveApps/sdk/main/LICENSE.md
curl -L -o THIRD_PARTY_LICENSES/LGPL-3.0.txt https://www.gnu.org/licenses/lgpl-3.0.txt
curl -L -o THIRD_PARTY_LICENSES/GPL-3.0.txt  https://www.gnu.org/licenses/gpl-3.0.txt
```

…and make sure `scripts/build.py` bundles them:

```python
    licenses = ROOT / "THIRD_PARTY_LICENSES"
    if licenses.is_dir():
        cmd += ["--add-data", f"{licenses}{SEP}THIRD_PARTY_LICENSES"]
```

### Disclaimer

THIS SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR IMPLIED,
INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY, FITNESS FOR A
PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE AUTHORS BE LIABLE FOR
ANY CLAIM, DAMAGES OR OTHER LIABILITY, INCLUDING **DATA LOSS**, ARISING FROM THE USE
OF THIS SOFTWARE.

Deletion — especially permanent deletion — is irreversible. **Keep your own backup
before using the delete feature.** You are responsible for complying with Proton's
Terms of Service when using this tool with your account.

> [!NOTE]
> **AI-assisted ("vibecoded").** Built with AI coding assistants (Anthropic Claude,
> Qwen 3.8 Max / 4 Max) directed by FroggyWarrior. There is **no line-by-line human code
> audit** — the code is validated by running it and checking that it behaves as described.
> The app itself contains **no AI**. Treat it as experimental and keep your own backups.
> See [AI use in this project](#ai-use-in-this-project).

## Credits

Developed by **FroggyWarrior**.

Built on the official [Proton Drive SDK and CLI](https://github.com/ProtonDriveApps/sdk)
by Proton AG, and on [Qt for Python](https://wiki.qt.io/Qt_for_Python).

Issues and pull requests are welcome: <https://github.com/FroggyWarrior/neutron-migrator/issues>