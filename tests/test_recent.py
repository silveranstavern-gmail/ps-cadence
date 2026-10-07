import re

import pytest

from tts_reader.engine import Engine
from tts_reader.server import create_app
from tts_reader.storage import Store


def test_remove_recent_survives_bookmarks_and_restart_and_reopen_restores(tmp_path):
    path = tmp_path / 'chapter.txt'
    path.write_text('One two three.', encoding='utf-8')
    store = Store(tmp_path / 'data')
    doc = store.open_path(path)
    other = store.import_text('Clipboard text', 'Another reading.')
    store.remove_recent(doc['id'])
    # Playback keeps saving positions after a user removes its current entry.
    store.bookmark(doc['id'], 2, 0.25)
    reopened_store = Store(tmp_path / 'data')
    assert [entry['id'] for entry in reopened_store.recent()] == [other['id']]
    assert reopened_store.document(doc['id'])['bookmark'] == {'word': 2, 'offset': 0.25}
    assert reopened_store.document(doc['id'])['reloadable']
    restored = reopened_store.open_path(path)
    assert restored['id'] == doc['id']
    assert restored['bookmark'] == {'word': 2, 'offset': 0.25}
    assert len(reopened_store.recent()) == 2
    assert path.read_text(encoding='utf-8') == 'One two three.'


def test_clear_recent_includes_older_entries_and_preserves_readings(tmp_path):
    store = Store(tmp_path)
    docs = [store.import_text('Clipboard text', f'Unique reading {n}.') for n in range(25)]
    assert len(store.recent()) == 20
    assert len(store.recent(limit=None)) == 25
    store.clear_recent()
    store.bookmark(docs[-1]['id'], 1, 0.4)
    assert Store(tmp_path).recent(limit=None) == []
    assert all(store.document(doc['id'])['text'] == doc['text'] for doc in docs)
    assert store.document(docs[-1]['id'])['bookmark'] == {'word': 1, 'offset': 0.4}
    # Repeating the operation on an empty list is harmless.
    store.clear_recent()
    store.import_text('Clipboard text', docs[0]['text'])
    assert [entry['id'] for entry in store.recent()] == [docs[0]['id']]
    with pytest.raises(KeyError):
        store.remove_recent('unknown')


def test_recent_api_authorization_and_full_list(tmp_path):
    store = Store(tmp_path / 'data')
    docs = [store.import_text('Clipboard text', f'Reading {n}.') for n in range(25)]
    engine = Engine(tmp_path / 'data')
    assets = tmp_path / 'ui'
    assets.mkdir()
    (assets / 'index.html').write_text('<html><!--BOOTSTRAP--></html>')
    app = create_app(store, engine, assets, tmp_path / 'sample.txt')
    client = app.test_client()
    try:
        assert client.get('/api/recent').status_code == 403
        token = re.search(r'"token": "([^"]+)"', client.get('/').text).group(1)
        headers = {'X-Reader-Token': token}
        assert len(client.get('/api/recent').json) == 25
        assert client.get('/api/recent').json[0]['preview'].startswith('Reading ')
        assert client.post('/api/recent/remove', json={'document': docs[0]['id']}).status_code == 403
        assert client.post('/api/recent/clear', json={}).status_code == 403
        assert len(store.recent(limit=None)) == 25
        for body in ({}, [], {'document': 1}):
            assert client.post('/api/recent/remove', json=body, headers=headers).status_code == 400
        assert client.post('/api/recent/remove', json={'document': 'missing'}, headers=headers).status_code == 404
        assert client.post('/api/recent/remove', json={'document': docs[0]['id']}, headers=headers).status_code == 200
        assert len(client.get('/api/recent').json) == 24
        assert client.get(f'/api/document/{docs[0]["id"]}').status_code == 200
        assert client.post('/api/recent/clear', json={}, headers=headers).status_code == 200
        assert client.get('/api/state').json['recent'] == []
        assert client.get('/api/recent').json == []
    finally:
        engine.close()
