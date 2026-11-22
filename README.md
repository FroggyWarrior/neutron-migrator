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
- [Use cases](#use-cases)
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
  (defaults: English + system theme). All strings live in JSON files, so new languages are
  drop-in.
- **Honest errors**: every failure shows a readable message plus a *Show more* panel
  with copyable, secret-redacted debug information (always in English).

## Use cases

Neutron Migrator moves the **photo timeline** of a Proton account to a local folder, and
optionally removes it from the cloud afterwards. That makes it useful for:

- **Proton → Proton.** Moving photos between accounts (personal → family, splitting a
  shared account, leaving an old address). Download while signed in as account A, sign
  out, sign in as B, then upload with Proton's own tools
  (`proton-drive photo upload --help`, or the mobile/desktop app).
- **Proton → somewhere else.** Export the whole library once, then import it into a
  different provider with that provider's own client. See
  [alternatives](#open-source-end-to-end-encrypted-alternatives) below.
- **Offline backup (3-2-1).** Keep a local copy on your disk or NAS while staying on
  Proton. Nothing is deleted unless you explicitly choose to.
- **Reclaiming space.** Download everything, verify the copy, then move the cloud side to
  the trash — recoverable — and only later delete permanently.

It does **not** touch Mail, Calendar, Contacts, Pass, Docs or VPN, and it does not upload
anything: it is an export-and-cleanup tool, not a sync client.

### Why stay in Proton

- **End-to-end encryption by default** across Drive, Photos, Mail, Calendar and Pass, with
  zero-access encryption on the server side. No ads, no data selling; the business model
  is subscriptions.
- **One account, one bill** for mail, calendar, storage, password manager, aliases, VPN,
  docs and 2FA. If you use several of them, the bundle is hard to beat on price and
  convenience.
- **Swiss jurisdiction** with GDPR alignment, and a long public track record of fighting
  legal requests rather than quietly complying.
- **Open-source clients and published audits**, plus — since 2026 — an official
  [Drive SDK and CLI](https://github.com/ProtonDriveApps/sdk) that makes automation
  possible at all. This application exists because of that.
- **A mature mail ecosystem**: custom domains, catch-all, aliases, IMAP/SMTP via Bridge,
  and desktop/mobile clients that work today.
- **Photos that just work** on mobile: automatic backup, albums, sharing, all encrypted.
- **Recovery options** (recovery phrase, recovery file, recovery email) that mitigate the
  main risk of zero-knowledge storage: forgetting your password.

### Why leave Proton

Not a recommendation — just the reasons people actually cite. Portability cuts both ways,
and this tool is meant to make either direction easy.

- **All your eggs in one basket.** A single account holds your mail, calendar, contacts,
  files, photos, passwords, 2FA seeds and VPN. A suspension, a billing failure, a
  compromised password or a locked account takes *everything* down at once. An offline
  export is cheap insurance, whatever you decide.
- **Zero-knowledge also means zero rescue.** Lose the password without a working recovery
  method and the data is gone; support cannot decrypt it for you.
- **"Open source" means the clients, not the service.** The server side is proprietary.
  The Drive SDK/CLI was only published in 2026 and its own README still says it is *not
  ready for third-party production use*, with a breaking cryptographic migration
  announced for end-2026/early-2027 that will stop older clients from interoperating.
- **No standard access protocols.** There is no WebDAV, no S3 endpoint, no official rclone
  backend. Automation depends entirely on Proton's own CLI, which is why a wrapper like
  this one is needed in the first place.
- **Linux is a second-class citizen.** There is still no official Proton Drive desktop
  app for Linux — announced, but unavailable; the CLI only arrived in June 2026. Mail has
  no official desktop client either (Bridge is mail-only). Proton VPN, to be fair, does
  ship a proper Linux app.
- **Breadth over depth** (community perception, not a measurable fact): Pass, Docs,
  Sheets, Wallet, Authenticator, Lumo and Meet have shipped while long-standing Drive
  requests — a Linux client, selective sync, better photo tooling — keep waiting.
- **Leadership and the AI push.** A [404 Media investigation](https://www.404media.co/manifestos-fear-and-loser-thinking-inside-protons-ai-reckoning/)
  reported internal messages in which CEO Andy Yen told engineers to "stop lovingly
  handcrafting all our code", dismissed security objections as "loser thinking", and pushed
  to skip penetration testing in favour of "AI velocity", alongside plans to re-interview
  staff about their AI use with implications for their jobs; employees described a culture
  where raising security concerns was discouraged. After user backlash and subscription
  cancellations, Proton **cancelled those re-interviews and apologised**, stating that "AI
  will never be at the expense of security" — while keeping the shift towards AI-assisted
  development, with CTO Bart Butler arguing that "programming is dead, but engineering is
  not". For a company whose product is trust, that episode is a reason to keep your own
  copies regardless of where you store them.

### Open-source, end-to-end encrypted alternatives

All of these publish their source code and encrypt on the client. Licences, quotas and
features change: check the repositories before committing. **None of them import from
Proton directly** — export here, then upload with the destination's own client, and
verify a small batch before deleting anything.

| Option | Pros | Cons |
|---|---|---|
| **[Ente Photos](https://ente.io)** | The closest match for this tool's use case: photo/video-first, E2EE, client **and** server open source (AGPL), albums, on-device face/object search, desktop apps for Linux/Windows/macOS, mobile auto-backup, self-hostable | Photos and videos only — not a general-purpose file drive; smaller company; self-hosting needs Postgres + object storage |
| **[Filen](https://filen.io)** | E2EE (AES-256-GCM), real sync clients including Linux, WebDAV and S3 gateways, mobile photo backup, German/EU jurisdiction | Clients are open source but the server code is not published; no dedicated photos app with albums; smaller ecosystem |
| **[Internxt](https://internxt.com)** | E2EE with post-quantum key exchange, client and server code published, Drive + Send + Mail + VPN bundle, EU jurisdiction | Long-standing complaints about speed and reliability; aggressive lifetime-plan marketing; Linux desktop support has lagged behind (CLI available) |
| **[Seafile](https://www.seafile.com)** | Very mature self-hosted sync, per-library E2EE, excellent Linux clients, handles large libraries well | ⚠️ Encrypted libraries are second-class: no web preview or search, and **mobile auto-backup cannot upload into them** — good as a migration target, not as an E2EE phone backup; you run and maintain the server |
| **[Peergos](https://peergos.org)** | E2EE, peer-to-peer, fully open source, self-hostable, no central storage provider | Small project, fewer clients and integrations, slower photo workflows |
| **[Syncthing](https://syncthing.net/)** | Similar to Peergos, as it's E2EE, peer-to-peer, fully open source, self-hostable, no central storage provider | ⚠️ No photo backups, just folder sync |
| **[Cryptomator](https://cryptomator.org) + any storage** | Keep your existing cloud/NAS and add an audited E2EE vault on top; open source, cross-platform; no migration of provider needed | No photo app, albums or auto-backup; you manage sync yourself; large libraries mean many encrypted files |
| **[MEGA](https://mega.io)** | E2EE, generous free tier, native Linux clients, source code published | ⚠️ Its published code uses a **custom, restrictive licence, not an OSI-approved one**, and the server is proprietary — so it only half-meets the "open source" bar. Included because people ask about it |

Two different bars: **all** of the above work as a destination for the photos you export
here (you upload from the desktop). If you also want **automatic, end-to-end encrypted
backup from your phone** afterwards, only Ente, Filen and Internxt offer that today —
verify before committing, since these apps change fast.

Excluded on purpose: Tresorit, pCloud, Sync.com, Icedrive and Koofr are not open source;
Immich is excellent and open source but **not** end-to-end encrypted (the server sees your
photos); **Nextcloud** has E2EE only as an opt-in, experimental per-folder feature, and its
mobile auto-upload does not target encrypted folders — so your photo backup would not be
zero-knowledge.

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