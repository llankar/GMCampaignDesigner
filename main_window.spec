# -*- mode: python ; coding: utf-8 -*-
from PyInstaller.building.datastruct import Tree

a = Analysis(
    ['main_window.py'],
    pathex=[],
    binaries=[],
    datas=[
        ('assets', 'assets'),
        ('config', 'config'),
        ('static', 'static'),
        ('scripts', 'scripts'),
        ('modules/ui/webview/templates/browser_shell.html', 'modules/ui/webview/templates'),
        ('modules/ui/webview/static/browser_shell.css', 'modules/ui/webview/static'),
        ('modules/ui/webview/static/browser_shell.js', 'modules/ui/webview/static'),
    ],
    hiddenimports=['modules.ui.webview.pywebview_launcher'],
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

update_analysis = Analysis(
    ['scripts/update_entry.py'],
    pathex=['scripts'],
    binaries=[],
    datas=[],
    hiddenimports=[],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=['torch', 'torchvision', 'torchaudio', 'onnx', 'transformers', 'simplejson'],
    noarchive=False,
    optimize=0,
)
update_pyz = PYZ(update_analysis.pure)

update_exe = EXE(
    update_pyz,
    update_analysis.scripts,
    [],
    exclude_binaries=True,
    name='RPGCampaignUpdater',
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
)
coll = COLLECT(
    exe,
    update_exe,
    a.binaries,
    a.datas,
    update_analysis.binaries,
    update_analysis.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='RPGCampaignManager',
)
