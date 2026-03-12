[Setup]
; ═══════════════════════════════════════════════════════════════════════════
; Sivas Belediyesi Evrak Yönetim Sistemi — Kurulum Sihirbazı (Inno Setup)
; ═══════════════════════════════════════════════════════════════════════════

AppId={{8A7B6C5D-4E3F-2A1B-9C0D-E8F7A6B5C4D3}}
AppName=Sivas Belediyesi Evrak Yönetim Sistemi
AppVersion=8.0
AppPublisher=Sivas Belediyesi Bilgi İşlem
AppPublisherURL=https://www.sivas.bel.tr/
AppSupportURL=https://www.sivas.bel.tr/
AppUpdatesURL=https://www.sivas.bel.tr/

; Kurulum dizini
DefaultDirName={sd}\SivasBelediyesiDMS
DefaultGroupName=Sivas Belediyesi
DisableProgramGroupPage=yes

; Çıkış ayarları
OutputDir=.\InnoOutput
OutputBaseFilename=SivasBelediyesiDMS_Kurulum_v8.0
SetupIconFile=assets\icon.ico
Compression=lzma2/ultra64
SolidCompression=yes
ArchitecturesInstallIn64BitMode=x64

; İzinler (Veritabanı yazma/okuma sorunu olmaması için C:\ hedeflendi ve yetki verildi)
PrivilegesRequired=admin

[Languages]
Name: "turkish"; MessagesFile: "compiler:Languages\Turkish.isl"

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"; Flags: checkedonce

[Files]
; Ana uygulama dizinindeki her şeyi kopyala
Source: "dist\SivasBelediyesiDMS\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Dirs]
; Klasöre tam okuma/yazma (SQLite için) izni veriyoruz
Name: "{app}"; Permissions: everyone-full
Name: "{app}\evrak_arsiv"; Permissions: everyone-full

[Icons]
; Başlat Menüsü İkonu
Name: "{group}\Sivas Belediyesi Evrak Yönetim Sistemi"; Filename: "{app}\SivasBelediyesiDMS.exe"; IconFilename: "{app}\assets\icon.ico"
; Masaüstü İkonu
Name: "{autodesktop}\Sivas Belediyesi Evrak Yönetim Sistemi"; Filename: "{app}\SivasBelediyesiDMS.exe"; Tasks: desktopicon; IconFilename: "{app}\assets\icon.ico"

[Run]
; Kurulum bittikten sonra çalıştır seçeneği
Filename: "{app}\SivasBelediyesiDMS.exe"; Description: "{cm:LaunchProgram,Sivas Belediyesi Evrak Yönetim Sistemi}"; Flags: nowait postinstall skipifsilent
