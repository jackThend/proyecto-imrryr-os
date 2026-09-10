; Imrryr OS — Inno Setup Script
#define MyAppName "Imrryr OS"
#define MyAppVersion "1.0.0"
#define MyAppPublisher "Imrryr OS"
#define MyAppURL "http://localhost:3000"
#define MyAppExeName "Iniciar Imrryr OS.exe"
#ifndef MyAppProfile
  #define MyAppProfile "pyme"
#endif

[Setup]
AppId={{657FCC94-E6CC-4E4E-A72A-8FE81B16EC51}}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher={#MyAppPublisher}
AppPublisherURL={#MyAppURL}
PrivilegesRequired=lowest
DefaultDirName={localappdata}\Programs\{#MyAppName}
DefaultGroupName={#MyAppName}
DisableProgramGroupPage=yes
OutputDir=C:\Users\caosd\Desktop\Proyectos Software\Proyecto Imrryr OS\imrryr-os\dist
OutputBaseFilename=Imrryr_OS_Setup_{#MyAppProfile}
Compression=lzma2/max
SolidCompression=yes
WizardStyle=modern

[Languages]
Name: "spanish"; MessagesFile: "compiler:Languages\Spanish.isl"

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"

[Files]
Source: "C:\Users\caosd\Desktop\Proyectos Software\Proyecto Imrryr OS\imrryr-os\dist\imrryr-os-pkg\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{group}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"
Name: "{group}\Detener Imrryr OS"; Filename: "{app}\Detener Imrryr OS.exe"
Name: "{autodesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; Tasks: desktopicon
Name: "{autodesktop}\Detener Imrryr OS"; Filename: "{app}\Detener Imrryr OS.exe"; Tasks: desktopicon

[Run]
Filename: "{app}\{#MyAppExeName}"; Description: "{cm:LaunchProgram,{#StringChange(MyAppName, '&', '&&')}}"; Flags: nowait postinstall skipifsilent

[UninstallRun]
Filename: "{app}\Detener Imrryr OS.exe"; Flags: runhidden waituntilterminated
