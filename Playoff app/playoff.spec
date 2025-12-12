# -*- mode: python ; coding: utf-8 -*-
import os
import sys

# PyInstaller onefile extrahuje do MEIPASS
project_dir = os.path.abspath(os.getcwd())

block_cipher = None

a = Analysis(
    ['playoff.py'],
    pathex=[project_dir],
    binaries=[],
    datas=[
        ('playoff.ico', '.'),     # IKONA aplikace
        ('settings.ico', '.'),    # IKONA nastavení
        ('usb_module.py', '.'),   # USB modul
    ],
    hiddenimports=['PIL', 'PIL.Image', 'serial'],
    hookspath=[],
    runtime_hooks=[],
    excludes=[],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name='playoff',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    runtime_tmpdir=None,
    console=False,
    icon='playoff.ico'
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name='playoff'
)
