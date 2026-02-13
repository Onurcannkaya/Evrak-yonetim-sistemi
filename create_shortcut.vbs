Set oWS = WScript.CreateObject("WScript.Shell")
sLinkFile = oWS.SpecialFolders("Desktop") & "\Sivas Evrak Sistemi.lnk"
Set oLink = oWS.CreateShortcut(sLinkFile)
oLink.TargetPath = WScript.ScriptFullName
oLink.Arguments = ""
oLink.WorkingDirectory = CreateObject("Scripting.FileSystemObject").GetParentFolderName(WScript.ScriptFullName)
oLink.IconLocation = "shell32.dll,165"
oLink.Description = "Sivas Belediyesi - Akilli Evrak Yonetim Sistemi v4.0"
oLink.Save

' Batch dosyasının yolunu al
strBatchPath = CreateObject("Scripting.FileSystemObject").GetParentFolderName(WScript.ScriptFullName) & "\Evrak_Sistemi_Baslat.bat"

' Kısayolu batch dosyasına yönlendir
Set oLink = oWS.CreateShortcut(sLinkFile)
oLink.TargetPath = strBatchPath
oLink.WorkingDirectory = CreateObject("Scripting.FileSystemObject").GetParentFolderName(WScript.ScriptFullName)
oLink.IconLocation = "imageres.dll,1"
oLink.Description = "Sivas Belediyesi - Akilli Evrak Yonetim Sistemi v4.0"
oLink.Save

WScript.Echo "Masaustu kisayolu olusturuldu!"
