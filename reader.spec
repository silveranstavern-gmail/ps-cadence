# Build on Windows. Use build.ps1 -Cpu for a CPU-only distributable.
from pathlib import Path
from PyInstaller.utils.hooks import collect_all, collect_data_files

for required in ['vendor/speech-assets/manifest.json', 'vendor/webview2/msedgewebview2.exe']:
    if not Path(required).is_file():
        raise RuntimeError(f'Missing offline resource: {required}. Run prepare-runtime.ps1 first.')
datas = [('ui-dist', 'ui-dist'), ('demo.txt', '.'), ('assets/cadence.ico', 'assets'),
         ('vendor/speech-assets', 'speech-assets')]
binaries, hiddenimports = [], [
    'transformers.models.albert.modeling_albert',
    'transformers.models.albert.configuration_albert',
    'webview.platforms.edgechromium',
]
for package in ['kokoro', 'misaki', 'en_core_web_sm', 'espeakng_loader']:
    data, binary, imports = collect_all(package)
    datas += data
    binaries += binary
    hiddenimports += imports
datas += collect_data_files('webview')

a = Analysis(['app.py'], pathex=[], binaries=binaries, datas=datas,
             hiddenimports=hiddenimports, hookspath=[], hooksconfig={},
             excludes=['tkinter', 'PyQt5', 'PyQt6', 'PySide2', 'PySide6', 'tensorflow', 'jax',
                       'matplotlib', 'pandas', 'sklearn', 'torchvision', 'torchaudio', 'pytest', 'cv2'],
             noarchive=False)
pyz = PYZ(a.pure)
exe = EXE(pyz, a.scripts, [], exclude_binaries=True, name='Cadence',
          debug=False, bootloader_ignore_signals=False, strip=False, upx=False, console=False,
          icon='assets/cadence.ico', version='assets/windows-version.txt')
coll = COLLECT(exe, a.binaries, a.datas, strip=False, upx=False, name='Cadence')
# Fixed WebView2 is copied unchanged after analysis by packaging_resources.py.
