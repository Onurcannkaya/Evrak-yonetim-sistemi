import os
import sys
import winshell
from win32com.client import Dispatch

def create_shortcut():
    desktop = winshell.desktop()
    path = os.path.join(desktop, "Evrak Yönetim Sistemi.lnk")
    target = os.path.abspath("gui_app.py")
    w_dir = os.path.dirname(target)
    icon = os.path.abspath("gui_app.py") # Python ikonu kullanır varsayılan olarak
    
    shell = Dispatch('WScript.Shell')
    shortcut = shell.CreateShortCut(path)
    shortcut.Targetpath = sys.executable
    shortcut.Arguments = f'"{target}"'
    shortcut.WorkingDirectory = w_dir
    shortcut.IconLocation = sys.executable
    shortcut.save()
    
    print(f"✅ Kısayol oluşturuldu: {path}")

if __name__ == "__main__":
    try:
        create_shortcut()
    except Exception as e:
        print(f"❌ Kısayol oluşturulamadı: {e}")
        # Fallback: Batch dosyası
        with open("Baslat.bat", "w") as f:
            f.write(f'@echo off\npython "{os.path.abspath("gui_app.py")}"\npause')
        print("Alternatif olarak 'Baslat.bat' oluşturuldu.")
