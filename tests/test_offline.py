from pathlib import Path
import subprocess
import sys

import pytest

from tts_reader.engine import Engine
from tts_reader.runtime import require_speech_assets


def test_missing_model_has_reinstall_message_without_download(tmp_path):
    with pytest.raises(RuntimeError, match='Reinstall Cadence'):
        require_speech_assets(tmp_path)


def test_network_guard_blocks_hostnames_and_remote_ips_but_allows_loopback():
    # Audit hooks cannot be removed: exercise in a child process.
    result = subprocess.run([sys.executable, '-c', '''
import socket
from tts_reader.runtime import configure_offline
configure_offline()
assert socket.getaddrinfo('127.0.0.1', 80)
for host in ('huggingface.co', '1.1.1.1'):
    try:
        socket.getaddrinfo(host, 443)
    except OSError as error:
        assert 'offline' in str(error)
    else:
        raise AssertionError('External address resolution allowed')
try:
    socket.socket().connect(('1.1.1.1', 443))
except OSError as error:
    assert 'offline' in str(error)
else:
    raise AssertionError('External connection allowed')
'''], capture_output=True, text=True, timeout=20)
    assert result.returncode == 0, result.stderr


def test_auto_retries_gpu_failure_once_and_stays_on_cpu(tmp_path, monkeypatch):
    engine = Engine(tmp_path)
    calls = []
    monkeypatch.setitem(sys.modules, 'torch', type('Torch', (), {
        'cuda': type('Cuda', (), {'empty_cache': staticmethod(lambda: None)})})())
    def synth(chunk, voice):
        calls.append(engine._cpu_fallback)
        if not engine._cpu_fallback:
            engine._attempted_device = 'cuda'
            raise RuntimeError('CUDA out of memory')
        engine.actual_device = 'cpu'
        return 'audio', 'timings'
    monkeypatch.setattr(engine, '_synthesize_once', synth)
    try:
        assert engine.synthesize({}, 'bm_lewis') == ('audio', 'timings')
        engine.synthesize({}, 'af_heart')
        assert calls == [False, True, True]
        assert engine.actual_device == 'cpu'
        assert 'CPU' in engine.device_notice
    finally:
        engine.close()


@pytest.mark.parametrize('device,attempted', [('cuda', 'cuda'), ('cpu', 'cpu'), ('auto', None)])
def test_explicit_device_or_asset_error_is_not_hidden(tmp_path, monkeypatch, device, attempted):
    engine = Engine(tmp_path, device=device)
    engine._attempted_device = attempted
    calls = []
    def fail(*args):
        calls.append(True)
        raise RuntimeError('original failure')
    monkeypatch.setattr(engine, '_synthesize_once', fail)
    try:
        with pytest.raises(RuntimeError, match='original failure'):
            engine.synthesize({}, 'bm_lewis')
        assert len(calls) == 1
    finally:
        engine.close()
