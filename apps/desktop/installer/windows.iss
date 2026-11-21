; Adle for Windows: the installer, made with Inno Setup (https://jrsoftware.org/isinfo.php).
;
; Compiled by scripts/installer.mjs, which passes everything that changes from one build to
; the next:
;
;   ISCC /DAppVersion=0.1.0-alpha.1 /DNumericVersion=0.1.0.0 /DSourceDir=<the release folder>
;        /DOutputDir=<where the installer goes> /DOutputName=<its name, without .exe>
;        /DIconFile=<icon.ico> windows.iss
;
; What it does, and what it leaves alone (ADR-034):
;   - installs for the person running it, under their own programs folder. No administrator
;     is asked for, and nothing is written for anyone else on the computer;
;   - asks Adle and its background service to close before their files are replaced;
;   - removes on uninstall what it installed. The learner's courses and settings are kept
;     elsewhere (%APPDATA%\Adle) and are never touched by installing or uninstalling.
; Nothing here is signed, and nothing looks for updates.

#ifndef AppVersion
  #error "AppVersion is not defined. Run this through scripts/installer.mjs."
#endif
#ifndef SourceDir
  #error "SourceDir is not defined. Run this through scripts/installer.mjs."
#endif

[Setup]
; What Windows knows this app by. It must never change: it is how a newer Adle is installed
; over an older one instead of beside it.
AppId={{4D3EAC0A-EE83-4838-8D7D-B683624971CA}
AppName=Adle
AppVersion={#AppVersion}
AppVerName=Adle {#AppVersion}
AppPublisher=XelXen
AppPublisherURL=https://github.com/XelXen/Adle
AppSupportURL=https://github.com/XelXen/Adle/issues
AppUpdatesURL=https://github.com/XelXen/Adle/releases
AppCopyright=Copyright (C) 2026 XelXen. GNU General Public License, version 3.
VersionInfoVersion={#NumericVersion}
VersionInfoProductName=Adle
VersionInfoDescription=Adle setup
PrivilegesRequired=lowest
DefaultDirName={autopf}\Adle
DisableProgramGroupPage=yes
UsePreviousAppDir=yes
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
MinVersion=10.0.17763
OutputDir={#OutputDir}
OutputBaseFilename={#OutputName}
SetupIconFile={#IconFile}
UninstallDisplayIcon={app}\Adle.exe
UninstallDisplayName=Adle
WizardStyle=modern
Compression=lzma2/max
SolidCompression=yes
LZMAUseSeparateProcess=yes
CloseApplications=yes
RestartApplications=no

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"; Flags: unchecked

[Files]
Source: "{#SourceDir}\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{autoprograms}\Adle"; Filename: "{app}\Adle.exe"
Name: "{autodesktop}\Adle"; Filename: "{app}\Adle.exe"; Tasks: desktopicon

[Run]
Filename: "{app}\Adle.exe"; Description: "{cm:LaunchProgram,Adle}"; Flags: nowait postinstall skipifsilent

[UninstallDelete]
; Anything the bundled Python wrote beside its own code while it ran. Only inside the
; folder that is Adle's alone: never the whole of the place it was installed to.
Type: filesandordirs; Name: "{app}\resources\core"
