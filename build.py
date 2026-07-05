import os
import shutil
import subprocess
from src.core.version import APP_NAME, APP_VERSION

def clean_build_dirs():
    print("Cleaning old build directories...")
    for dir_name in ['build', 'dist']:
        if os.path.exists(dir_name):
            shutil.rmtree(dir_name)

def generate_spec():
    print("Generating PyInstaller spec...")
    spec_content = f"""# -*- mode: python ; coding: utf-8 -*-

block_cipher = None

a = Analysis(
    ['main.py'],
    pathex=[],
    binaries=[],
    datas=[
        ('alembic.ini', '.'),
        ('migrations', 'migrations')
    ],
    hiddenimports=[
        'sqlalchemy.sql.default_comparator',
        'alembic',
        'loguru',
        'PySide6',
        'src.database.base',
        'src.database.session',
        'src.database.audit_listener',
        'src.modules.inventory.models',
        'src.modules.crm.models',
        'src.modules.suppliers.models',
        'src.modules.purchasing.models',
        'src.modules.sales.models',
        'src.modules.finance.models',
        'src.modules.audit.models',
        'src.modules.authentication.models'
    ],
    hookspath=[],
    hooksconfig={{}},
    runtime_hooks=[],
    excludes=['pytest'],
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
    name='TAJ_FROID_ERP',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='TAJ_FROID_ERP',
)
"""
    with open('taj_froid.spec', 'w', encoding='utf-8') as f:
        f.write(spec_content)

def build_executable():
    print(f"Building {APP_NAME} v{APP_VERSION}...")
    try:
        subprocess.run(['pyinstaller', 'taj_froid.spec', '--noconfirm'], check=True)
        print("Build completed successfully.")
    except subprocess.CalledProcessError as e:
        print(f"Build failed with error: {e}")
        exit(1)

if __name__ == "__main__":
    clean_build_dirs()
    generate_spec()
    build_executable()
