"""Exercise the offline installer, installed desktop/speech, and safe uninstall."""
import argparse
import json
import os
from pathlib import Path
import subprocess
import sys
import time
import winreg


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--installer', type=Path,
                        default=Path('dist/installers/Cadence-0.2.0-Windows11-x64-Offline-Setup.exe'))
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    # Do not redirect an existing real installation's uninstall registration.
    key = r'Software\Microsoft\Windows\CurrentVersion\Uninstall\{826A88BC-E29A-48C3-AD32-7F1CC16E3BF1}_is1'
    try:
        existing = winreg.OpenKey(winreg.HKEY_CURRENT_USER, key, 0, winreg.KEY_READ | winreg.KEY_WOW64_64KEY)
    except FileNotFoundError:
        pass
    else:
        existing.Close()
        raise RuntimeError('Cadence is already installed. Run this lifecycle test on a separate Windows account.')
    data = root / '.reader-data' / 'installer-verification' / str(time.time_ns())
    target = data / 'Installed copy, café'
    data.mkdir(parents=True)
    assert target.resolve().is_relative_to(data.resolve())
    env = os.environ.copy()
    env['PATH'] = str(Path(os.environ['WINDIR']) / 'System32')
    env['HTTP_PROXY'] = env['HTTPS_PROXY'] = 'http://127.0.0.1:9'
    env['NO_PROXY'] = '127.0.0.1,localhost'
    report = {'installer': str(args.installer.resolve()), 'directory': str(target), 'steps': []}
    def run(command, timeout=600):
        subprocess.run(command, env=env, check=True, timeout=timeout, creationflags=subprocess.CREATE_NO_WINDOW)
    try:
        install_args = [str(args.installer.resolve()), '/VERYSILENT', '/SUPPRESSMSGBOXES', '/NORESTART',
                        '/NOICONS', f'/DIR={target}', f'/LOG={data / "install.log"}']
        run(install_args)
        exe = target / 'Cadence.exe'
        assert exe.is_file() and (target / '_internal' / 'webview2' / 'msedgewebview2.exe').is_file()
        report['steps'].append('install')
        print('Offline installer completed.', flush=True)
        run([sys.executable, '-m', 'tests.smoke_offline', '--exe', str(exe), '--desktop', '--expect-device', 'cuda'])
        report['steps'].append('installed desktop and all six GPU voices')
        before = sorted((root / '.reader-data' / 'offline-verification').glob('*/verification.json'))[-1]
        library = before.parent / 'data' / 'library.sqlite3'
        assert library.is_file()
        library_bytes = library.read_bytes()
        run(install_args)
        assert library.read_bytes() == library_bytes
        report['steps'].append('reinstall preserves library')
        print('Reinstall preserved the reading library.', flush=True)
    finally:
        uninstaller = target / 'unins000.exe'
        if uninstaller.is_file():
            # Inno only removes files in its installation log, inside this owned
            # test directory. Never run an uninstaller from a redirected path.
            assert uninstaller.resolve().is_relative_to(data.resolve())
            run([str(uninstaller), '/VERYSILENT', '/SUPPRESSMSGBOXES', '/NORESTART',
                 f'/LOG={data / "uninstall.log"}'])
            assert not (target / 'Cadence.exe').exists()
            if 'library' in locals():
                assert library.read_bytes() == library_bytes
            report['steps'].append('uninstall preserves library')
            print('Uninstall completed; reading library preserved.', flush=True)
        (data / 'verification.json').write_text(json.dumps(report, indent=2), encoding='utf-8')
        print(f'Installer report: {data / "verification.json"}', flush=True)


if __name__ == '__main__':
    main()
