from __future__ import annotations

import hashlib
import json
import re
import secrets
from pathlib import Path

from flask import Flask, abort, jsonify, request, send_file

from .engine import Engine, SAMPLE_RATE
from .storage import Store, VOICES


def create_app(store: Store, engine: Engine, assets: Path, sample: Path) -> Flask:
    app = Flask(__name__, static_folder=None)
    app.config['MAX_CONTENT_LENGTH'] = 6_000_000
    token, nonce = secrets.token_urlsafe(32), secrets.token_urlsafe(24)
    cookie_name = f'tts_reader_{secrets.token_hex(6)}'

    @app.before_request
    def protect_local_app():
        if request.host.split(':')[0] not in ('127.0.0.1', 'localhost'):
            abort(403)
        if request.path.startswith('/api/'):
            if not secrets.compare_digest(request.cookies.get(cookie_name, ''), token):
                abort(403)
            if request.method != 'GET' and not secrets.compare_digest(request.headers.get('X-Reader-Token', ''), token):
                abort(403)

    @app.after_request
    def response_headers(response):
        response.headers['X-Content-Type-Options'] = 'nosniff'
        response.headers['Content-Security-Policy'] = (
            f"default-src 'self'; script-src 'self' 'nonce-{nonce}'; style-src 'self' 'unsafe-inline'; "
            "img-src 'self' data:; media-src 'self' blob:; connect-src 'self'; frame-ancestors 'none'; object-src 'none'"
        )
        if request.path.startswith('/api/') and '/audio/' not in request.path:
            response.headers['Cache-Control'] = 'no-store'
        return response

    @app.errorhandler(ValueError)
    def invalid(error):
        return jsonify(error=str(error)), 400

    @app.errorhandler(KeyError)
    def missing(error):
        return jsonify(error='This text could not be found.'), 404

    @app.errorhandler(OSError)
    def file_error(error):
        return jsonify(error=f'Could not read the file: {error.strerror or str(error)}'), 400

    @app.errorhandler(413)
    def too_large(error):
        return jsonify(error='Please select a text file smaller than 5 MB.'), 413

    @app.get('/')
    def index():
        path = assets / 'index.html'
        if not path.is_file():
            return 'Build the reader interface first: npm install && npm run build', 503
        bootstrap = json.dumps({'token': token}).replace('<', '\\u003c')
        html = path.read_text(encoding='utf-8').replace('<!--BOOTSTRAP-->',
            f'<script nonce="{nonce}">window.READER_BOOT={bootstrap};</script>')
        response = app.make_response(html)
        response.set_cookie(cookie_name, token, httponly=True, samesite='Strict')
        response.headers['Cache-Control'] = 'no-store'
        return response

    @app.get('/assets/<path:name>')
    def asset(name):
        path = (assets / 'assets' / name).resolve()
        if not path.is_relative_to((assets / 'assets').resolve()) or not path.is_file():
            abort(404)
        return send_file(path)

    @app.get('/api/state')
    def state():
        return jsonify(settings=store.settings(), recent=store.recent(), voices=VOICES)

    @app.get('/api/recent')
    def recent_texts():
        return jsonify(store.recent(limit=None))

    @app.post('/api/recent/remove')
    def remove_recent():
        data = request.get_json()
        if not isinstance(data, dict) or not isinstance(data.get('document'), str):
            raise ValueError('Choose a text to remove from the list.')
        store.remove_recent(data['document'])
        return jsonify(ok=True)

    @app.post('/api/recent/clear')
    def clear_recent():
        store.clear_recent()
        return jsonify(ok=True)

    @app.post('/api/import')
    def import_text():
        data = request.get_json()
        if not isinstance(data, dict) or not isinstance(data.get('text'), str):
            raise ValueError('Please provide plain text.')
        return jsonify(store.import_text(str(data.get('name', 'Untitled.txt')), data['text']))

    @app.post('/api/sample')
    def load_sample():
        return jsonify(store.import_text('Sample text.txt', sample.read_text(encoding='utf-8')))

    @app.get('/api/document/<doc_id>')
    def document(doc_id):
        return jsonify(store.document(doc_id))

    @app.post('/api/reload/<doc_id>')
    def reload(doc_id):
        return jsonify(store.reload(doc_id))

    def chosen_voice(data):
        voice = data.get('voice', store.settings()['voice'])
        if voice not in VOICES:
            raise ValueError('Unknown voice.')
        return voice

    @app.post('/api/prepare')
    def prepare():
        data = request.get_json()
        engine.prepare(store.document(data['document']), chosen_voice(data), int(data.get('chunk', 0)))
        return jsonify(ok=True)

    @app.post('/api/cancel')
    def cancel():
        engine.cancel_pending()
        return jsonify(ok=True)

    @app.get('/api/jobs/<doc_id>')
    def jobs(doc_id):
        return jsonify(engine.snapshot(store.document(doc_id), chosen_voice(request.args)))

    @app.post('/api/bookmark')
    def bookmark():
        data = request.get_json()
        store.bookmark(data['document'], int(data['word']), float(data.get('offset', 0)))
        return jsonify(ok=True)

    @app.post('/api/settings')
    def settings():
        data = request.get_json()
        if not isinstance(data, dict):
            raise ValueError('Invalid settings.')
        return jsonify(store.save_settings(data))

    @app.get('/api/audio/<key>')
    def audio(key):
        if not re.fullmatch(r'[a-f0-9]{64}', key) or not engine.cached(key):
            abort(404)
        return send_file(engine.directory / f'{key}.wav', mimetype='audio/wav', conditional=True)

    @app.get('/api/export/<doc_id>')
    def export(doc_id):
        import soundfile as sf
        doc = store.document(doc_id)
        voice = chosen_voice(request.args)
        keys = [engine.key(c, voice) for c in doc['chunks']]
        if not all(engine.cached(k) for k in keys):
            return jsonify(error='Prepare all audio before exporting.'), 409
        exports = store.directory / 'exports'
        exports.mkdir(exist_ok=True)
        signature = hashlib.sha256(''.join(keys).encode()).hexdigest()[:12]
        path = exports / f'{doc_id}-{voice}-{signature}.wav'
        if not path.is_file():
            tmp = exports / f'{doc_id}-{voice}-{signature}-{secrets.token_hex(4)}.tmp'
            with sf.SoundFile(tmp, mode='w', samplerate=SAMPLE_RATE, channels=1, format='WAV', subtype='PCM_16') as out:
                for key in keys:
                    with sf.SoundFile(engine.directory / f'{key}.wav') as source:
                        for block in source.blocks(blocksize=65_536):
                            out.write(block)
            tmp.replace(path)
        if not path.with_suffix('.json').is_file():
            # Export companion preserves global audio times and original visible word IDs.
            timeline, offset = [], 0.0
            for chunk, key in zip(doc['chunks'], keys):
                cached = engine.cached(key)
                for timing in cached['timings']:
                    word = doc['words'][chunk['word_start'] + timing['local_word']]
                    timeline.append({'word': word['id'], 'text': word['text'],
                                     'start': round(offset + timing['start'], 4),
                                     'end': round(offset + timing['end'], 4), 'approximate': timing['approximate']})
                offset += cached['duration']
            path.with_suffix('.json').write_text(json.dumps({'text': doc['text'], 'voice': voice,
                'sample_rate': SAMPLE_RATE, 'words': timeline}, ensure_ascii=False, indent=2), encoding='utf-8')
        filename = f'{Path(doc["name"]).stem}-{voice}.wav'
        return send_file(path, mimetype='audio/wav', as_attachment=True, download_name=filename)

    @app.get('/api/export-timings/<doc_id>')
    def export_timings(doc_id):
        doc = store.document(doc_id)
        voice = chosen_voice(request.args)
        keys = [engine.key(c, voice) for c in doc['chunks']]
        signature = hashlib.sha256(''.join(keys).encode()).hexdigest()[:12]
        path = store.directory / 'exports' / f'{doc_id}-{voice}-{signature}.json'
        if not path.is_file():
            return jsonify(error='Export the WAV first to create its timing companion.'), 409
        return send_file(path, mimetype='application/json', as_attachment=True,
                         download_name=f'{Path(doc["name"]).stem}-{voice}.json')

    return app
