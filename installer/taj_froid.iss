[Setup]
AppName=TAJ FROID ERP
AppVersion=1.0.0-rc1
AppPublisher=TAJ FROID
DefaultDirName={autopf}\TAJ_FROID_ERP
DefaultGroupName=TAJ FROID ERP
OutputDir=..\dist
OutputBaseFilename=TajFroidERP_Setup_v1.0.0-rc1
Compression=lzma
SolidCompression=yes
ArchitecturesAllowed=x64
ArchitecturesInstallIn64BitMode=x64
PrivilegesRequired=admin
DisableProgramGroupPage=yes

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"; Flags: unchecked

[Files]
Source: "..\dist\TAJ_FROID_ERP\TAJ_FROID_ERP.exe"; DestDir: "{app}"; Flags: ignoreversion
Source: "..\dist\TAJ_FROID_ERP\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs
; NOTE: Don't use "Flags: ignoreversion" on any shared system files

[Icons]
Name: "{group}\TAJ FROID ERP"; Filename: "{app}\TAJ_FROID_ERP.exe"
Name: "{group}\{cm:UninstallProgram,TAJ FROID ERP}"; Filename: "{uninstallexe}"
Name: "{autodesktop}\TAJ FROID ERP"; Filename: "{app}\TAJ_FROID_ERP.exe"; Tasks: desktopicon

[Run]
Filename: "{app}\TAJ_FROID_ERP.exe"; Description: "{cm:LaunchProgram,TAJ FROID ERP}"; Flags: nowait postinstall skipifsilent

[UninstallDelete]
; Crucially, we DO NOT delete %LOCALAPPDATA%\TAJ_FROID. 
; The customer database, backups, and logs must be preserved across uninstalls and upgrades.
Type: filesandordirs; Name: "{app}"
