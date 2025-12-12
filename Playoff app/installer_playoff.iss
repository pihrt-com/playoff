[Setup]
AppName=Playoff
AppVersion=1.0.6
DefaultDirName={pf}\Playoff
DefaultGroupName=Playoff
OutputDir=output_installer
OutputBaseFilename=PlayoffSetup_1.0.6
Compression=lzma
SolidCompression=yes
AppPublisher=Martin Pihrt
AppPublisherURL=https://github.com/pihrt-com/playoff
AppSupportURL=https://github.com/pihrt-com/playoff
AppUpdatesURL=https://github.com/pihrt-com/playoff
ShowLanguageDialog=no
WizardImageFile=instalator_logo.bmp
WizardImageStretch=yes
WizardStyle=modern

[Languages]
Name: "czech"; MessagesFile: "compiler:Languages\Czech.isl"

[Files]
Source: "dist\playoff.exe"; DestDir: "{app}"; Flags: ignoreversion
Source: "dist\updater.exe"; DestDir: "{app}"; Flags: ignoreversion
Source: "playoff.ico"; DestDir: "{app}"; Flags: ignoreversion

[Icons]
Name: "{group}\Playoff"; Filename: "{app}\playoff.exe"; IconFilename: "{app}\playoff.ico"
Name: "{userdesktop}\Playoff"; Filename: "{app}\playoff.exe"; IconFilename: "{app}\playoff.ico"; Tasks: desktopicon

[Tasks]
Name: "desktopicon"; Description: "Vytvořit zástupce na ploše"; GroupDescription: "Další volby:"; Flags: unchecked