#define MyAppName "Yash CRM"
#define MyAppVersion "1.1.0"
#define MyAppPublisher "Yash CRM"
#define MyAppExeName "YashCRM.exe"
[Setup]
AppId={{A0B47B7E-7B43-4D75-9805-7A74BB7CF06B}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher={#MyAppPublisher}
DefaultDirName={autopf}\Yash CRM
DefaultGroupName=Yash CRM
DisableProgramGroupPage=yes
OutputDir=..\release
OutputBaseFilename=YashCRM-Setup-1.1.0
SetupIconFile=..\static\icons\app.ico
UninstallDisplayIcon={app}\{#MyAppExeName}
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
PrivilegesRequired=lowest
PrivilegesRequiredOverridesAllowed=dialog
[Files]
Source: "..\dist\YashCRM.exe"; DestDir: "{app}"; Flags: ignoreversion
[Icons]
Name: "{autoprograms}\Yash CRM"; Filename: "{app}\{#MyAppExeName}"; WorkingDir: "{app}"
Name: "{autodesktop}\Yash CRM"; Filename: "{app}\{#MyAppExeName}"; WorkingDir: "{app}"; Tasks: desktopicon
[Tasks]
Name: "desktopicon"; Description: "Create a &desktop shortcut"; GroupDescription: "Additional icons:"; Flags: checkedonce
[Run]
Filename: "{app}\{#MyAppExeName}"; Description: "Launch Yash CRM"; Flags: nowait postinstall skipifsilent
