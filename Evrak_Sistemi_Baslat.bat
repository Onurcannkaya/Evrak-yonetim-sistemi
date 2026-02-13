@echo off
REM Sivas Belediyesi - Akıllı Evrak Sistemi Başlatıcı
REM Versiyon: 5.0

echo ====================================
echo Sivas Belediyesi
echo Akilli Evrak Yonetim Sistemi v5.0
echo ====================================
echo.
echo Sistem baslatiliyor...
echo.

REM Çalışma dizinine git
cd /d "%~dp0"

REM Python ile GUI'yi başlat
python gui_app.py

REM Hata durumunda pencereyi açık tut
if errorlevel 1 (
    echo.
    echo HATA: Sistem baslatilirken bir sorun olustu.
    echo Lutfen Python 3.12'nin yuklu oldugunu dogrulayin.
    echo.
    pause
)
