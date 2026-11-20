**Neutron Migrator 1.0.3** — download or delete all your Proton Drive photos.

Sign-in happens in your browser through the **official Proton Drive CLI** (bundled, checksum-verified), so CAPTCHA, 2FA, security keys and two-password mode are handled by Proton itself. No password ever touches this app.

*This is a third-party application, not officially supported by Proton.*

### Downloads

| Platform | File | Requirements |
|---|---|---|
| Windows x64 | `NeutronMigrator-windows-x64.zip` | Windows 10 1809+ / 11 |
| Windows ARM64 | `NeutronMigrator-windows-arm64.zip` | Windows 11 on ARM |
| Linux x86_64 | `NeutronMigrator-linux-x86_64.AppImage` or `...-linux-x64.tar.gz` | glibc 2.34+, libsecret + Secret Service (GNOME Keyring / KWallet) |
| Linux ARM64 | `NeutronMigrator-linux-aarch64.AppImage` or `...-linux-arm64.tar.gz` | glibc 2.39+, libsecret + Secret Service |
| macOS Apple Silicon | `NeutronMigrator-macos-arm64.dmg` | macOS 14+ |
| macOS Intel | `NeutronMigrator-macos-x64.dmg` | macOS 14+ |

macOS builds are unsigned: right-click → **Open** the first time.

### Features

- Browser sign-in; session stored in the OS keychain.
- Preview of photo count and total size before any action.
- Download to a folder of your choice, with progress bar and cancel.
- Delete to trash, or permanently (only the selected photos; duplicate names in the Photos trash are skipped and reported).
- English / Spanish, dark / light / system theme.
- Errors include a "Show more" panel with copyable debug info.

Built with PySide6 and the official Proton Drive SDK CLI. Developed by FroggyWarrior.
