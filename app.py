from __future__ import annotations

import argparse
import logging
from logging.handlers import RotatingFileHandler
import json
import os
import signal
import sys
import threading
import webbrowser
from pathlib import Path

from werkzeug.serving import make_server

from tts_reader.engine import Engine
from tts_reader.server import create_app
from tts_reader.storage import Store
from tts_reader.runtime import configure_offline, configure_webview, resource_root


APP_NAME = 'P.S. | Cadence'


class DesktopApi:
    def __init__(self, store):
        self._store = store
        self._window = None

    def open_file(self):
        import webview
        paths = self._window.create_file_dialog(webview.FileDialog.OPEN, allow_multiple=False,
                                               file_types=('Text and Markdown (*.txt;*.md)', 'Text files (*.txt)', 'Markdown files (*.md)'))
        if not paths:
            return None
        try:
            return self._store.open_path(paths[0])
        except Exception as error:
            return {'error': str(error)}

    def read_clipboard(self):
        from tts_reader.clipboard import read_text
        try:
            return {'text': read_text()}
        except Exception as error:
            return {'error': str(error)}


def main():
    parser = argparse.ArgumentParser(description='Sepia reader with local Kokoro speech')
    parser.add_argument('--browser', action='store_true', help='Use a browser instead of a desktop window')
    parser.add_argument('--no-open', action='store_true', help='Start the server without opening a window')
    parser.add_argument('--port', type=int, default=0, help='Local port; default chooses a free port')
    parser.add_argument('--data-dir', type=Path)
    parser.add_argument('--input', type=Path, help='Open a text or Markdown file at launch')
    parser.add_argument('--device', choices=['auto', 'cpu', 'cuda'], default='auto')
    parser.add_argument('--ui-smoke-report', type=Path, help=argparse.SUPPRESS)
    args = parser.parse_args()
    configure_offline()
    resources = resource_root()
    data = args.data_dir or Path(os.environ.get('LOCALAPPDATA', str(Path.home() / '.local' / 'share'))) / 'TTSReader'
    data.mkdir(parents=True, exist_ok=True)
    # pythonw/PyInstaller's windowless bootloader leaves these streams as None.
    # Kokoro's Loguru setup requires a real stderr even without a console window.
    if sys.stdout is None or sys.stderr is None:
        console_log = open(data / 'reader-console.log', 'a', encoding='utf-8', buffering=1)
        if sys.stdout is None:
            sys.stdout = console_log
        if sys.stderr is None:
            sys.stderr = console_log
    logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s %(message)s',
                        handlers=[RotatingFileHandler(data / 'reader.log', maxBytes=2_000_000, backupCount=2,
                                                      encoding='utf-8'), logging.StreamHandler()])
    logging.getLogger('werkzeug').setLevel(logging.WARNING)
    store = Store(data)
    if args.input:
        store.open_path(args.input)
    engine = Engine(data, device=args.device)
    sample = resources / ('demo.txt' if getattr(sys, 'frozen', False) else 'sample.txt')
    app = create_app(store, engine, resources / 'ui-dist', sample)
    server = make_server('127.0.0.1', args.port, app, threaded=True)
    thread = threading.Thread(target=server.serve_forever, name='reader-http', daemon=True)
    thread.start()
    url = f'http://127.0.0.1:{server.server_port}/'
    print(f'{APP_NAME}: {url}', flush=True)
    stopped = threading.Event()

    def stop(*_):
        stopped.set()

    signal.signal(signal.SIGINT, stop)
    signal.signal(signal.SIGTERM, stop)
    try:
        if args.browser or args.no_open:
            if not args.no_open:
                webbrowser.open(url)
            stopped.wait()
        else:
            if sys.platform == 'win32':
                # Keep the taskbar icon separate from Python when running from source.
                import ctypes
                ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID('PS.Cadence')
            import webview
            configure_webview(webview, resources, data)
            api = DesktopApi(store)
            api._window = webview.create_window(APP_NAME, url, js_api=api, width=1120, height=850,
                                               min_size=(560, 500), background_color='#f5eddc')
            if args.ui_smoke_report:
                def check_window():
                    import time
                    report = {'ok': False}
                    try:
                        for _ in range(100):
                            report = api._window.evaluate_js('({title: document.title, voices: document.querySelector("#voice")?.options.length, userAgent: navigator.userAgent, bridge: !!window.pywebview?.api})') or {}
                            if report.get('voices') == 6 and report.get('bridge'):
                                report['ok'] = True
                                break
                            time.sleep(0.1)
                        report['runtime'] = webview.settings['WEBVIEW2_RUNTIME_PATH']
                        args.ui_smoke_report.write_text(json.dumps(report, indent=2), encoding='utf-8')
                    finally:
                        api._window.destroy()
                api._window.events.loaded += check_window
            webview.start(gui='edgechromium', icon=str(resources / 'assets' / 'cadence.ico'),
                          private_mode=False, storage_path=str(data / 'webview2'))
    finally:
        engine.close()
        server.shutdown()
        server.server_close()


if __name__ == '__main__':
    try:
        main()
    except Exception:
        logging.exception('Cadence could not start')
        if sys.platform == 'win32' and '--no-open' not in sys.argv and '--ui-smoke-report' not in sys.argv:
            import ctypes
            ctypes.windll.user32.MessageBoxW(None,
                'Cadence could not start. Reinstall the complete offline package.\n\n'
                'Details are in %LOCALAPPDATA%\\TTSReader\\reader.log.', APP_NAME, 0x10)
        raise
