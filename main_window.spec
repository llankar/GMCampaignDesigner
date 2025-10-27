# -*- mode: python ; coding: utf-8 -*-
a = Analysis(
    ['main_window.py'],
    pathex=[],
    binaries=[],
    datas=[
        ('assets', 'assets'),
        ('config', 'config'),
        ('static', 'static'),
        ('scripts', 'scripts'),
        ('modules', 'modules'),
        ('modules', '_internal/modules'),
        ('docs', 'docs'),
        ('version.txt', '.'),
    ],
    hiddenimports=[],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=['torch', 'torchvision', 'torchaudio', 'onnx', 'transformers', 'simplejson'],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='RPGCampaignManager',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=True,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    version='version.txt',
    icon='assets/GMCampaignDesigner.ico'
)
coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    Tree('assets', prefix='assets'),
    Tree('config', prefix='config'),
    Tree('static', prefix='static'),
    Tree('scripts', prefix='scripts'),
    Tree('docs', prefix='docs'),
    Tree('modules', prefix='modules'),
    Tree('modules', prefix='_internal/modules'),
    strip=False,
    upx=True,
    upx_exclude=[],
    name='RPGCampaignManager',
)

