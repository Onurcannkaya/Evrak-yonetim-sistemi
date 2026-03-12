# -*- mode: python ; coding: utf-8 -*-
# ═══════════════════════════════════════════════════════════════════════════
#  Sivas Belediyesi — Evrak Yönetim Sistemi v8.0
#  PyInstaller Build Specification (OneDir - No Internal Folder)
# ═══════════════════════════════════════════════════════════════════════════

import sys
import os

block_cipher = None

# Projenin kök dizini
ROOT = os.path.dirname(os.path.abspath(SPEC))

a = Analysis(
    [os.path.join(ROOT, 'main_app.py')],
    pathex=[ROOT],
    binaries=[],
    datas=[
        # Config ve Veritabanı
        (os.path.join(ROOT, 'config.json'), '.'),
        (os.path.join(ROOT, 'evrak_yonetim.db'), '.'),
        # Kaynak Klasörleri
        (os.path.join(ROOT, 'ui'), 'ui'),
        (os.path.join(ROOT, 'assets'), 'assets'),
    ],
    hiddenimports=[
        'PyQt6.QtWidgets', 'PyQt6.QtCore', 'PyQt6.QtGui', 'PyQt6.sip',
        'google.genai', 'google.auth', 'google.auth.transport.requests',
        'PIL', 'PIL.Image', 'PIL._imaging', 'fitz',
        'openpyxl', 'openpyxl.styles', 'openpyxl.utils',
        'sqlite3', 'json', 'hashlib', 'pathlib', 'logging', 
        'urllib.parse', 'webbrowser'
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        # İstenmeyen ağır kütüphaneler (performans için)
        'easyocr', 'pytesseract', 'paddleocr', 'torch', 'torchvision',
        'cv2', 'numpy', 'scipy', 'sklearn', 'tensorflow', 'keras',
        'tkinter', 'matplotlib', 'pandas'
    ],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='SivasBelediyesiDMS',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,                # Terminal penceresini kapatır
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    # === İkon ===
    icon=os.path.join(ROOT, 'assets', 'icon.ico') if os.path.exists(os.path.join(ROOT, 'assets', 'icon.ico')) else None,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='SivasBelediyesiDMS',
    # Bu parametre v6.0+ için _internal klasörünü kapatır:
    contents_directory='.'
)
