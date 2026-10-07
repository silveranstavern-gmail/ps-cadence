"""Quick frozen executable check; smoke_offline covers the full offline release."""
import argparse
import http.cookiejar
import json
import re
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--source-windowless', action='store_true')
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    data = root / '.reader-data' / ('source-windowless-check' if args.source_windowless else 'portable-check') / str(time.time_ns())
    executable = root / 'dist' / 'Cadence' / 'Cadence.exe'
    command = [str(Path(sys.executable).with_name('pythonw.exe')), str(root / 'app.py')] if args.source_windowless else [str(executable)]
    port = 52137 if args.source_windowless else 52135
    process = subprocess.Popen([*command, '--no-open', '--port', str(port), '--data-dir', str(data)],
                               creationflags=subprocess.CREATE_NO_WINDOW)
    opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(http.cookiejar.CookieJar()))
    base = f'http://127.0.0.1:{port}'
    try:
        home = None
        until = time.monotonic() + 25
        while time.monotonic() < until:
            if process.poll() is not None:
                raise RuntimeError(f'The bundle exited before starting: {process.returncode}')
            try:
                home = opener.open(base, timeout=2).read().decode()
                break
            except (OSError, urllib.error.URLError):
                time.sleep(0.25)
        if not home:
            raise RuntimeError('The portable app did not start.')
        token = re.search(r'"token": "([^"]+)"', home).group(1)
        def request(path, body=None, headers=None):
            headers = {**(headers or {})}
            if body is not None:
                headers.update({'Content-Type': 'application/json', 'X-Reader-Token': token})
            return opener.open(urllib.request.Request(base + path, data=None if body is None else json.dumps(body).encode(), headers=headers), timeout=20)
        print('Windowless source app started.' if args.source_windowless else 'Portable executable started.', flush=True)
        sample = json.load(request('/api/sample', {}))
        assert sample['words']
        if not args.source_windowless:
            assert 'Mira' in sample['text']
        doc = json.load(request('/api/import', {'name': 'Portable verification.md',
            'text': '# Speech verification\n\nThe lantern glowed **softly**. Ian [opened](https://example.com) his eyes. Talent: `3200→3300!`'}))
        assert doc['format'] == 'markdown'
        assert all(marker not in doc['text'] for marker in ('#', '**', '`', 'https://'))
        request('/api/prepare', {'document': doc['id'], 'voice': 'bm_lewis', 'chunk': 0}).close()
        print('Generating real speech.', flush=True)
        start = time.monotonic()
        until = start + 120
        while time.monotonic() < until:
            state = json.load(request(f'/api/jobs/{doc["id"]}?voice=bm_lewis'))
            errors = [c.get('error') for c in state['chunks'] if c['status'] == 'error']
            if errors:
                raise RuntimeError(f'Bundled generation failed: {errors}')
            if state['ready'] == state['total']:
                break
            time.sleep(0.3)
        else:
            raise RuntimeError('Bundled generation timed out.')
        assert state['device'] in ('cpu', 'cuda')
        word_timings = [t for c in state['chunks'] for t in c['timings']]
        assert len(word_timings) == len(doc['words'])
        number = next(w['id'] for w in doc['words'] if '3200' in w['text'])
        assert not next(t for t in word_timings if t['word'] == number)['approximate']
        audio = request(state['chunks'][0]['url'], headers={'Range': 'bytes=0-99'})
        assert audio.status == 206 and len(audio.read()) == 100
        assert request(f'/api/export/{doc["id"]}?voice=bm_lewis').read()[:4] == b'RIFF'
        report = {'device': state['device'], 'passages': state['total'], 'words': len(word_timings),
                  'audio_seconds': round(sum(c['duration'] for c in state['chunks']), 3),
                  'elapsed_seconds': round(time.monotonic() - start, 3), 'range_and_export': 'passed'}
        (data / 'verification.json').write_text(json.dumps(report, indent=2), encoding='utf-8')
        print(json.dumps(report), flush=True)
    finally:
        process.terminate()
        process.wait(timeout=10)


if __name__ == '__main__':
    main()
