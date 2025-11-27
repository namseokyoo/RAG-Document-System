# -*- mode: python ; coding: utf-8 -*-
from PyInstaller.utils.hooks import collect_all

datas = [('resources', 'resources'), ('models', 'models'), ('libs', 'libs')]
binaries = []
hiddenimports = [
    'win32timezone',
    'sentencepiece',
    'chromadb.api.segment',
    'chromadb.api.types',
    'chromadb.segment.impl.vector.local_persistent_hnsw',
    'tiktoken_ext.openai_public',
    'tiktoken_ext',
    'pkg_resources'
]

# Collect all chromadb
tmp_ret = collect_all('chromadb')
datas += tmp_ret[0]
binaries += tmp_ret[1]
hiddenimports += tmp_ret[2]

# Collect all langchain
tmp_ret = collect_all('langchain')
datas += tmp_ret[0]
binaries += tmp_ret[1]
hiddenimports += tmp_ret[2]

# Collect all langchain_community
tmp_ret = collect_all('langchain_community')
datas += tmp_ret[0]
binaries += tmp_ret[1]
hiddenimports += tmp_ret[2]

# Collect all sentence_transformers
tmp_ret = collect_all('sentence_transformers')
datas += tmp_ret[0]
binaries += tmp_ret[1]
hiddenimports += tmp_ret[2]

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
    name='RAG_System_v0.5.0',
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
    icon=['resources/oc.ico'],
)
coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='RAG_System_v0.5.0',
)
