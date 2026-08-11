; ===========================================================================
; Inno Setup Script
; PROJECT : Autodesk Industry Model to PostgreSQL/PostGIS Connector
; PHASE   : Phase 6 - Deployment & Industrialization
; ===========================================================================
;
; INSTRUCTIONS:
;   1. Install Inno Setup from https://jrsoftware.org/ispage.php (free)
;   2. Build the .exe first:  python scripts/build_exe.py
;   3. Open this file in Inno Setup Compiler and click Build > Compile
;   4. Find the installer in:  installer_output/Setup_AutodeskPostgreSQLConnector.exe
; ===========================================================================

[Setup]
AppId={{B7F3A1C2-4E2D-4F1A-91C3-A2B3C4D5E6F7}
AppName=Autodesk PostgreSQL Connector
AppVersion=1.0.0
AppPublisher=cec projekt GmbH
AppPublisherURL=https://www.cec-projekt.de
AppCopyright=Copyright (C) 2025

; Installation directory (Program Files by default)
DefaultDirName={autopf}\Autodesk PostgreSQL Connector
DefaultGroupName=Autodesk PostgreSQL Connector

; Require administrator privileges for installation
PrivilegesRequired=admin

; Output installer file
OutputDir=installer_output
OutputBaseFilename=Setup_AutodeskPostgreSQLConnector

; Compression
Compression=lzma2/ultra64
SolidCompression=yes
InternalCompressLevel=ultra64

; Installer appearance
WizardStyle=modern
SetupIconFile=

; Minimum Windows version: Windows 10
MinVersion=10.0

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Files]
; Main executable (compiled by PyInstaller)
Source: "dist\AutodeskPostgreSQLConnector.exe"; DestDir: "{app}"; Flags: ignoreversion

; Optional: README / User Guide
; Source: "Phase 6-Implementation-Testing\06-testing-user-guide_EN.md"; DestDir: "{app}"; Flags: ignoreversion

[Icons]
; Start Menu shortcut
Name: "{group}\Autodesk PostgreSQL Connector";           Filename: "{app}\AutodeskPostgreSQLConnector.exe"
Name: "{group}\Uninstall Autodesk PostgreSQL Connector"; Filename: "{uninstallexe}"

; Desktop shortcut (optional)
Name: "{commondesktop}\Autodesk PostgreSQL Connector";   Filename: "{app}\AutodeskPostgreSQLConnector.exe"; Tasks: desktopicon

; Windows Startup shortcut — auto-start at every Windows logon
Name: "{userstartup}\Autodesk PostgreSQL Connector";     Filename: "{app}\AutodeskPostgreSQLConnector.exe"

[Tasks]
Name: "desktopicon"; Description: "Create a &desktop shortcut"; GroupDescription: "Additional icons:"

[Run]
; Launch the application immediately after installation finishes
Filename: "{app}\AutodeskPostgreSQLConnector.exe"; Description: "Launch Autodesk PostgreSQL Connector now"; Flags: nowait postinstall skipifsilent

[UninstallRun]
; Kill the process before uninstalling
Filename: "taskkill"; Parameters: "/F /IM AutodeskPostgreSQLConnector.exe"; Flags: runhidden

[UninstallDelete]
; Clean up config and log files
Type: files; Name: "{app}\connector_config.json"
Type: files; Name: "{app}\connector.log"

[Messages]
FinishedHeadingLabel=Installation complete!
FinishedLabelNoIcons=The Autodesk PostgreSQL Connector has been installed and is now running in the system tray (near the clock). You can right-click the tray icon to configure your PostgreSQL connection.
