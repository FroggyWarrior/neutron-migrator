#define AppName "Neutron Migrator"
#define AppVersion "1.0.4"
#define AppExe "Neutron Migrator.exe"

[Setup]
AppId={{7C4E1B92-3A5D-4F0E-9B6A-2D8C1F5A0E31}
AppName={#AppName}
AppVersion={#AppVersion}
AppPublisher=FroggyWarrior
DefaultDirName={autopf}\NeutronMigrator
DefaultGroupName={#AppName}
OutputDir=..\..\dist
OutputBaseFilename=NeutronMigrator-windows-arm64-setup
Compression=lzma2/max
SolidCompression=yes
WizardStyle=modern
PrivilegesRequired=lowest
ArchitecturesAllowed=arm64
ArchitecturesInstallIn64BitMode=x64compatible

[Languages]
Name: "en"; MessagesFile: "compiler:Default.isl"
Name: "es"; MessagesFile: "compiler:Languages\Spanish.isl"

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; Flags: unchecked

[Files]
Source: "..\..\dist\Neutron Migrator\*"; DestDir: "{app}"; Flags: recursesubdirs ignoreversion

[Icons]
Name: "{group}\{#AppName}"; Filename: "{app}\{#AppExe}"
Name: "{autodesktop}\{#AppName}"; Filename: "{app}\{#AppExe}"; Tasks: desktopicon

[Run]
Filename: "{app}\{#AppExe}"; Description: "{cm:LaunchProgram,{#AppName}}"; Flags: nowait postinstall skipifsilent