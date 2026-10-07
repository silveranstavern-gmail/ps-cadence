"""Test a real frozen release with empty caches and no external Python networking.

Run again with --disable-cuda --expect-device cpu to exercise auto CPU selection.
This does not substitute for disconnected clean-machine/driver compatibility QA.
"""
import argparse
import array
import http.cookiejar
import io
import json
import os
from pathlib import Path
import re
import socket
import subprocess
import time
import urllib.request
import wave


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--exe', type=Path, default=Path('dist/Cadence/Cadence.exe'))
    parser.add_argument('--device', choices=['auto', 'cpu', 'cuda'], default='auto')
    parser.add_argument('--expect-device', choices=['cpu', 'cuda'])
    parser.add_argument('--disable-cuda', action='store_true')
    parser.add_argument('--desktop', action='store_true')
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    data = root / '.reader-data' / 'offline-verification' / str(time.time_ns())
    data.mkdir(parents=True)
    env = os.environ.copy()
    for key in ('PYTHONPATH', 'PYTHONHOME', 'CUDA_PATH', 'CUDA_HOME'):
        env.pop(key, None)
    env.update({'PATH': str(Path(os.environ['WINDIR']) / 'System32'),
                'HF_HOME': str(data / 'empty-hf'), 'HF_HUB_CACHE': str(data / 'empty-hf' / 'hub'),
                'HUGGINGFACE_HUB_CACHE': str(data / 'empty-hf' / 'hub'),
                'TRANSFORMERS_CACHE': str(data / 'empty-transformers'),
                'TORCH_HOME': str(data / 'empty-torch'), 'HF_HUB_OFFLINE': '1',
                'TRANSFORMERS_OFFLINE': '1', 'HTTP_PROXY': 'http://127.0.0.1:9',
                'HTTPS_PROXY': 'http://127.0.0.1:9', 'NO_PROXY': 'localhost,127.0.0.1'})
    if args.disable_cuda:
        env['CUDA_VISIBLE_DEVICES'] = '-1'
    exe = args.exe.resolve()
    report = {'executable': str(exe), 'fresh_caches': True, 'developer_paths_removed': True,
              'device_requested': args.device, 'cuda_hidden': args.disable_cuda, 'voices': []}
    if args.desktop:
        ui_report = data / 'desktop.json'
        proc = subprocess.Popen([str(exe), '--data-dir', str(data / 'desktop-data'),
                                 '--ui-smoke-report', str(ui_report)], env=env,
                                creationflags=subprocess.CREATE_NO_WINDOW)
        try:
            code = proc.wait(timeout=120)
            if code or not ui_report.is_file():
                raise RuntimeError(f'Desktop startup failed: exit {code}, logs in {data}')
            report['desktop'] = json.loads(ui_report.read_text(encoding='utf-8'))
            assert report['desktop']['ok'], report['desktop']
            assert str(exe.parent / '_internal' / 'webview2') == report['desktop']['runtime']
            print('Fixed-runtime desktop interface passed.', flush=True)
        finally:
            if proc.poll() is None:
                proc.terminate()
                proc.wait(timeout=15)
    with socket.socket() as free_port:
        free_port.bind(('127.0.0.1', 0))
        port = free_port.getsockname()[1]
    process = subprocess.Popen([str(exe), '--no-open', '--port', str(port), '--device', args.device,
                                '--data-dir', str(data / 'data')], env=env,
                               creationflags=subprocess.CREATE_NO_WINDOW)
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}),
                                         urllib.request.HTTPCookieProcessor(http.cookiejar.CookieJar()))
    base = f'http://127.0.0.1:{port}'
    try:
        until = time.monotonic() + 90
        while True:
            try:
                home = opener.open(base, timeout=2).read().decode()
                break
            except OSError:
                if process.poll() is not None or time.monotonic() > until:
                    raise RuntimeError(f'Offline startup failed; logs in {data}')
                time.sleep(0.25)
        token = re.search(r'"token": "([^"]+)"', home).group(1)
        def request(path, body=None, headers=None):
            return opener.open(urllib.request.Request(base + path,
                data=json.dumps(body).encode() if body is not None else None,
                headers={'Content-Type': 'application/json', 'X-Reader-Token': token, **(headers or {})}), timeout=30)
        state = json.load(request('/api/state'))
        assert len(state['voices']) == 6
        doc = json.load(request('/api/import', {'name': 'Offline verification.md',
            'text': '# Offline speech\n\nThe lantern glowed **softly**. Ian opened his eyes. Talent: `3200→3300!`'}))
        assert doc['format'] == 'markdown'
        for voice in state['voices']:
            started = time.monotonic()
            request('/api/prepare', {'document': doc['id'], 'voice': voice, 'chunk': 0}).close()
            until = started + 180
            while True:
                jobs = json.load(request(f'/api/jobs/{doc["id"]}?voice={voice}'))
                errors = [c.get('error') for c in jobs['chunks'] if c['status'] == 'error']
                if errors:
                    raise RuntimeError(f'{voice}: {errors}')
                if jobs['ready'] == jobs['total']:
                    break
                if time.monotonic() > until:
                    raise RuntimeError(f'{voice}: speech timed out')
                time.sleep(0.2)
            if args.expect_device:
                assert jobs['device'] == args.expect_device, jobs['device']
            timings = [t for c in jobs['chunks'] for t in c['timings']]
            assert len(timings) == len(doc['words'])
            number = next(w['id'] for w in doc['words'] if '3200' in w['text'])
            assert not next(t for t in timings if t['word'] == number)['approximate']
            audio = request(jobs['chunks'][0]['url'], headers={'Range': 'bytes=0-99'})
            assert audio.status == 206 and len(audio.read()) == 100
            exported = request(f'/api/export/{doc["id"]}?voice={voice}').read()
            assert exported[:4] == b'RIFF' and len(exported) > 24000
            with wave.open(io.BytesIO(exported), 'rb') as wav:
                assert wav.getnchannels() == 1 and wav.getsampwidth() == 2 and wav.getframerate() == 24000
                samples = array.array('h', wav.readframes(wav.getnframes()))
                assert max(abs(value) for value in samples) > 100, 'Export contains silent audio.'
            info = {'voice': voice, 'device': jobs['device'], 'seconds': round(time.monotonic() - started, 3),
                    'audio_seconds': round(sum(c['duration'] for c in jobs['chunks']), 3),
                    'timing_range_export': 'passed'}
            report['voices'].append(info)
            print(json.dumps(info), flush=True)
        # The release must not populate a download cache, even though the
        # verification account's normal cache is intentionally unavailable.
        for folder in ('empty-hf', 'empty-transformers', 'empty-torch'):
            assert not any(p.is_file() for p in (data / folder).rglob('*'))
        report['passed'] = True
    finally:
        process.terminate()
        process.wait(timeout=15)
        (data / 'verification.json').write_text(json.dumps(report, indent=2), encoding='utf-8')
        print(f'Report: {data / "verification.json"}', flush=True)


if __name__ == '__main__':
    main()
