# -*- mode: python ; coding: utf-8 -*-
from PyInstaller.utils.hooks import collect_all

datas = [
    ('resources', 'resources'),
    ('config.json.example', '.'),
    ('models', 'models'),
    ('docs', 'docs'),
    ('libs/poppler/Library', 'libs/poppler/Library'),  # Poppler 번들링 (PDF Vision)
]
binaries = []
hiddenimports = ['win32timezone', 'sentencepiece', 'chromadb.api.segment', 'chromadb.api.types', 'chromadb.segment.impl.vector.local_persistent_hnsw']
tmp_ret = collect_all('chromadb')
datas += tmp_ret[0]; binaries += tmp_ret[1]; hiddenimports += tmp_ret[2]


a = Analysis(
    ['desktop_app.py'],
    pathex=[],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=['magic'],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='RAG_System_v0.3.7',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=True,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=['oc.ico'],
)
coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='RAG_System_v0.3.7',
)
