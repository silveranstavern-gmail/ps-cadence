#define AppVersion "0.2.0"
#define SourceRoot "..\dist\Cadence"

[Setup]
SetupArchitecture=x64
AppId={{826A88BC-E29A-48C3-AD32-7F1CC16E3BF1}
AppName=P.S. | Cadence
AppVersion={#AppVersion}
AppVerName=P.S. | Cadence {#AppVersion}
DefaultDirName={localappdata}\Programs\PS Cadence
DefaultGroupName=P.S. Cadence
PrivilegesRequired=lowest
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
MinVersion=10.0.22000
OutputDir=..\dist\installers
OutputBaseFilename=Cadence-{#AppVersion}-Windows11-x64-Offline-Setup
SetupIconFile=..\assets\cadence.ico
UninstallDisplayIcon={app}\Cadence.exe
Compression=lzma2/normal
SolidCompression=yes
LZMANumBlockThreads=4
WizardStyle=modern
DisableProgramGroupPage=yes
DisableWelcomePage=no
CloseApplications=yes
CloseApplicationsFilter=Cadence.exe
RestartApplications=no
SetupLogging=yes
InfoBeforeFile=installer-intro.txt

[Tasks]
Name: "desktopicon"; Description: "Create a desktop shortcut"; GroupDescription: "Shortcuts:"; Flags: unchecked

[Files]
Source: "{#SourceRoot}\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{group}\P.S. Cadence"; Filename: "{app}\Cadence.exe"
Name: "{autodesktop}\P.S. Cadence"; Filename: "{app}\Cadence.exe"; Tasks: desktopicon

[Run]
Filename: "{app}\Cadence.exe"; Description: "Launch P.S. Cadence"; Flags: nowait postinstall skipifsilent

[Code]
function InitializeSetup(): Boolean;
begin
  Result := not IsArm64;
  if not Result then
    MsgBox('This release requires Windows 11 on an Intel or AMD x64 computer.', mbError, MB_OK);
end;

// User readings and generated audio live outside the installation directory.
// Inno's uninstall log removes only files installed by this package.
