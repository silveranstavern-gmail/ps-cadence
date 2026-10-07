"""Resources and network policy for the self-contained Windows release."""
from __future__ import annotations

import ipaddress
import json
import os
from pathlib import Path
import sys

VERSION = '0.2.0'
MODEL_REVISION = 'f3ff3571791e39611d31c381e3a41a3af07b4987'
VOICE_IDS = ('bm_lewis', 'am_michael', 'af_heart', 'bf_emma', 'am_adam', 'bf_isabella')
_guard_installed = False


def resource_root() -> Path:
    return Path(getattr(sys, '_MEIPASS', Path(__file__).resolve().parents[1]))


def speech_root() -> Path:
    root = resource_root()
    return root / 'speech-assets' if getattr(sys, 'frozen', False) else root / 'vendor' / 'speech-assets'


def require_speech_assets(root: Path) -> None:
    expected = ['config.json', 'kokoro-v1_0.pth', *[f'voices/{v}.pt' for v in VOICE_IDS]]
    missing = [name for name in expected if not (root / name).is_file()]
    if missing:
        raise RuntimeError('Cadence speech files are missing. Reinstall Cadence from the complete offline installer. '
                           f'Missing: {", ".join(missing)}')


def _loopback(host) -> bool:
    if host in ('localhost', b'localhost', None):
        return True
    try:
        return ipaddress.ip_address(host.decode() if isinstance(host, bytes) else host).is_loopback
    except (ValueError, TypeError):
        return False


def _network_audit(event, args):
    # Enforce this below HTTP clients: a dependency cannot silently fetch a model
    # or send telemetry. The desktop interface uses only the loopback service.
    if event == 'socket.getaddrinfo' and not _loopback(args[0]):
        raise OSError('Cadence works offline; external network connections are disabled.')
    if event == 'socket.connect':
        address = args[1]
        if isinstance(address, tuple) and not _loopback(address[0]):
            raise OSError('Cadence works offline; external network connections are disabled.')


def configure_offline() -> None:
    global _guard_installed
    for key in ('HF_HUB_OFFLINE', 'TRANSFORMERS_OFFLINE', 'HF_HUB_DISABLE_TELEMETRY', 'DO_NOT_TRACK'):
        os.environ[key] = '1'
    if not _guard_installed:
        sys.addaudithook(_network_audit)
        _guard_installed = True


def configure_webview(webview, resources: Path, data: Path) -> None:
    fixed = resources / 'webview2'
    if not getattr(sys, 'frozen', False):
        fixed = resources / 'vendor' / 'webview2'
    if not (fixed / 'msedgewebview2.exe').is_file():
        raise RuntimeError('Cadence window files are missing. Reinstall the complete offline package.')
    webview.settings['WEBVIEW2_RUNTIME_PATH'] = str(fixed)
    webview.settings['ALLOW_DOWNLOADS'] = True
    # Force our tested runtime even if an unrelated application left overrides.
    os.environ['WEBVIEW2_BROWSER_EXECUTABLE_FOLDER'] = str(fixed)
    os.environ['WEBVIEW2_USER_DATA_FOLDER'] = str(data / 'webview2')
    os.environ['WEBVIEW2_ADDITIONAL_BROWSER_ARGUMENTS'] = (
        '--disable-background-networking --disable-component-update '
        '--disable-domain-reliability --disable-sync --no-first-run'
    )


def installation_info(resources: Path) -> dict:
    path = resources / 'release-manifest.json'
    return json.loads(path.read_text(encoding='utf-8')) if path.is_file() else {'version': VERSION}
