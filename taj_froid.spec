# -*- mode: python ; coding: utf-8 -*-

block_cipher = None

a = Analysis(
    ['main.py'],
    pathex=[],
    binaries=[],
    datas=[
        ('alembic.ini', '.'),
        ('migrations', 'migrations'),
        # The translation loader resolves resources/translations relative
        # to the frozen application root. Without this entry a packaged
        # build silently falls back to untranslated keys.
        ('resources/translations', 'resources/translations')
    ],
    hiddenimports=[
        'sqlalchemy.sql.default_comparator',
        'alembic',
        'loguru',
        'PySide6',
        'src.database.base',
        'src.database.session',
        'src.database.audit_listener',
        'src.core.system_service',
        'src.modules.inventory.models',
        'src.modules.crm.models',
        'src.modules.suppliers.models',
        'src.modules.purchasing.models',
        'src.modules.sales.models',
        'src.modules.finance.models',
        'src.modules.audit.models',
        'src.modules.authentication.models',
        'src.modules.authentication.bootstrap',
        'src.modules.pricing.models',
        'src.modules.settings.models',
        'src.modules.websync.services',
        'src.modules.websync.sync_config'
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    # The API and WebSocket prototype are not part of the desktop product.
    # Excluding them also keeps FastAPI/uvicorn out of the frozen binary.
    excludes=['pytest', 'tests', 'src.api', 'src.websocket'],
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
