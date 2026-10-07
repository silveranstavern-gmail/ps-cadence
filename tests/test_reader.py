import json
import re
import threading
import time
from pathlib import Path

import numpy as np
import pytest
import soundfile as sf

from tts_reader.engine import Engine, SAMPLE_RATE
from tts_reader.server import create_app
from tts_reader.storage import Store
from tts_reader.text import align_tokens, parse_text


def wait_for(predicate, timeout=5):
    until = time.monotonic() + timeout
    while time.monotonic() < until:
        if predicate():
            return
        time.sleep(0.01)
    raise AssertionError('Background task did not finish.')


def fake_speech(chunk, voice):
    timings = [{'local_word': n, 'start': n * 0.1, 'end': (n + 1) * 0.1, 'approximate': False}
               for n in range(len(chunk['local_words']))]
    return np.zeros(max(240, len(timings) * 2400), dtype=np.float32), timings


def test_chunks_preserve_display_words_and_source():
    source = '\ufeffIan said, “Go!”\r\n\r\n===\r\n\r\nTalent: 3200→3300!\r\n\r\n😀 Again again.'
    doc = parse_text(source, max_chars=25)
    assert [w['text'] for w in doc['words']] == ['Ian', 'said,', '“Go!”', 'Talent:', '3200→3300!', '😀', 'Again', 'again.']
    assert [n for c in doc['chunks'] for n in range(c['word_start'], c['word_end'])] == list(range(len(doc['words'])))
    assert all('===' not in c['text'] for c in doc['chunks'])
    assert doc['words'][2]['sentence'] != doc['words'][3]['sentence']


def test_subtokens_map_to_one_display_number_and_punctuation():
    words = [{'start': 0, 'end': 3}, {'start': 4, 'end': 13}, {'start': 14, 'end': 15}]
    spans = [{'char_start': 0, 'char_end': 3, 'start': 0.1, 'end': 0.4},
             {'char_start': 4, 'char_end': 8, 'start': 0.5, 'end': 1},
             {'char_start': 9, 'char_end': 13, 'start': 1.2, 'end': 1.8}]
    timing = align_tokens(words, spans, 2)
    assert timing[1] == {'local_word': 1, 'start': 0.5, 'end': 1.8, 'approximate': False}
    assert timing[2]['approximate'] and timing[2]['start'] == 1.8


def test_empty_text_rejected():
    with pytest.raises(ValueError, match='readable'):
        parse_text('\n\n===\n\n')


def test_bookmark_persists_and_changed_file_is_new_reading(tmp_path):
    store = Store(tmp_path / 'data')
    path = tmp_path / 'chapter.txt'
    path.write_text('One two three.', encoding='utf-8')
    doc = store.open_path(path)
    store.bookmark(doc['id'], 2, 0.25)
    assert store.reload(doc['id'])['bookmark'] == {'word': 2, 'offset': 0.25}
    store2 = Store(tmp_path / 'data')
    assert store2.document(doc['id'])['bookmark']['word'] == 2
    path.write_text('A different chapter.', encoding='utf-8')
    changed = store.reload(doc['id'])
    assert changed['id'] != doc['id']
    assert changed['bookmark']['word'] == 0


def test_settings_validation(tmp_path):
    store = Store(tmp_path)
    assert store.save_settings({'rate': 8, 'volume': -1})['rate'] == 2.5
    assert store.settings()['volume'] == 0
    with pytest.raises(ValueError):
        store.save_settings({'voice': '../bad'})
    with pytest.raises(ValueError):
        store.save_settings({'rate': float('nan')})


def test_utf16_file(tmp_path):
    path = tmp_path / 'chapter.txt'
    path.write_text('Ian saw 3200→3300.', encoding='utf-16')
    assert Store(tmp_path / 'data').open_path(path)['words'][-1]['text'] == '3200→3300.'


def test_relative_data_paths_are_absolute(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    store = Store(Path('relative-data'))
    engine = Engine(Path('relative-data'), synthesizer=fake_speech)
    try:
        assert store.directory.is_absolute()
        assert engine.directory.is_absolute()
    finally:
        engine.close()


def test_seek_prioritizes_new_passage_and_cache_survives_restart(tmp_path):
    entered, release = threading.Event(), threading.Event()
    calls = []
    doc = parse_text('First sentence.\n\nSecond sentence.\n\nThird sentence.', max_chars=19)
    def synth(chunk, voice):
        calls.append(chunk['index'])
        if len(calls) == 1:
            entered.set()
            assert release.wait(3)
        return fake_speech(chunk, voice)
    engine = Engine(tmp_path, synthesizer=synth)
    try:
        engine.prepare(doc, 'bm_lewis', 0)
        assert entered.wait(3)
        engine.prepare(doc, 'bm_lewis', 2)
        release.set()
        wait_for(lambda: engine.snapshot(doc, 'bm_lewis')['ready'] == 3)
        assert calls == [0, 2, 1]
        engine.prepare(doc, 'bm_lewis', 0)
        assert not engine.queue
    finally:
        release.set()
        engine.close()
    other = Engine(tmp_path, synthesizer=lambda *_: pytest.fail('Cache should be reused.'))
    try:
        assert other.snapshot(doc, 'bm_lewis')['ready'] == 3
        other.prepare(doc, 'bm_lewis', 0)
        assert not other.queue
        assert other.snapshot(doc, 'af_heart')['ready'] == 0
    finally:
        other.close()


def test_repeated_passage_is_generated_once(tmp_path):
    calls = []
    doc = parse_text('Same words.\n\nSame words.', max_chars=12)
    engine = Engine(tmp_path, synthesizer=lambda c,v: (calls.append(c['text']) or fake_speech(c,v)))
    try:
        engine.prepare(doc, 'bm_lewis', 0)
        wait_for(lambda: engine.snapshot(doc, 'bm_lewis')['ready'] == 2)
        assert len(calls) == 1
        assert engine.snapshot(doc, 'bm_lewis')['chunks'][1]['timings'][0]['word'] == 2
    finally:
        engine.close()


def test_api_auth_range_and_export(tmp_path):
    store = Store(tmp_path / 'data')
    engine = Engine(tmp_path / 'data', synthesizer=fake_speech)
    assets = tmp_path / 'ui'
    assets.mkdir()
    (assets / 'index.html').write_text('<html><!--BOOTSTRAP--></html>')
    sample = tmp_path / 'sample.txt'
    sample.write_text('Ian opened his eyes.\n\nTalent: 3200→3300!', encoding='utf-8')
    client = create_app(store, engine, assets, sample).test_client()
    try:
        assert client.get('/api/state').status_code == 403
        home = client.get('/')
        token = re.search(r'"token": "([^"]+)"', home.text).group(1)
        headers = {'X-Reader-Token': token}
        assert client.post('/api/sample', json={}).status_code == 403
        doc = client.post('/api/sample', json={}, headers=headers).json
        assert client.get('/api/state', headers={'Host': 'evil.test'}).status_code == 403
        assert client.get(f'/api/export/{doc["id"]}').status_code == 409
        assert client.post('/api/prepare', json={'document': doc['id'], 'voice': 'bm_lewis'}, headers=headers).status_code == 200
        wait_for(lambda: engine.snapshot(doc, 'bm_lewis')['ready'] == len(doc['chunks']))
        snapshot = client.get(f'/api/jobs/{doc["id"]}?voice=bm_lewis').json
        audio = client.get(snapshot['chunks'][0]['url'], headers={'Range': 'bytes=0-99'})
        assert audio.status_code == 206
        assert len(audio.data) == 100
        exported = client.get(f'/api/export/{doc["id"]}?voice=bm_lewis')
        assert exported.status_code == 200 and exported.data[:4] == b'RIFF'
        wav = next((store.directory / 'exports').glob('*.wav'))
        assert sf.info(wav).frames == sum(round(c['duration'] * SAMPLE_RATE) for c in snapshot['chunks'])
        timeline = json.loads(wav.with_suffix('.json').read_text(encoding='utf-8'))
        assert len(timeline['words']) == len(doc['words'])
        assert client.get(f'/api/export-timings/{doc["id"]}?voice=bm_lewis').status_code == 200
    finally:
        engine.close()
