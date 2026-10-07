import json
import sqlite3

import pytest

from tts_reader.markdown import markdown_to_text
from tts_reader.storage import Store


def test_markdown_maps_display_and_speech_to_the_same_clean_words(tmp_path):
    source = '''---
title: not narration
---
# A **quiet** morning

> Mira read [the news](https://example.com/private) &amp; smiled.

- [x] Bring *tea*
- Visit ~~old~~ friends and `Mira`.

| Item | Count |
| :--- | ---: |
| Apples | 3 |

![A small bird](bird.png)

```python
print("not narration")
```
'''
    store = Store(tmp_path)
    doc = store.import_text('Morning.MD', source)
    assert doc['format'] == 'markdown'
    assert 'A quiet morning' in doc['text']
    assert 'Mira read the news & smiled.' in doc['text']
    assert 'Bring tea' in doc['text'] and 'Visit old friends and Mira.' in doc['text']
    assert 'Item. Count.' in doc['text'] and 'Apples. 3.' in doc['text']
    assert 'A small bird' in doc['text']
    assert all(s not in doc['text'] for s in ('https:', 'bird.png', 'not narration', '**', '```', '|', '[x]'))
    assert [w['text'] for w in doc['words']] == [word for c in doc['chunks'] for word in c['text'].split()]
    assert [i for c in doc['chunks'] for i in range(c['word_start'], c['word_end'])] == list(range(len(doc['words'])))
    assert Store(tmp_path).document(doc['id'])['text'] == doc['text']
    assert Store(tmp_path).document(doc['id'])['format'] == 'markdown'


def test_html_is_plain_text_with_no_scripts_or_network_content():
    text = markdown_to_text('''# Safe

<div>Hello <b>world</b><br>Next line</div>

<script>secret()</script>

<style>not spoken</style>

Plain <span>text</span> and &lt;literal&gt;.
''')
    assert 'Hello world\nNext line' in text
    assert 'Plain text and <literal>.' in text
    assert 'secret' not in text and 'not spoken' not in text
    assert '<script' not in text and '<span' not in text


@pytest.mark.parametrize('source', ['```\nonly code\n```', '---\nkey: value\n---', '<script>only script</script>', '#\n\n***'])
def test_unreadable_markdown_leaves_existing_library_untouched(tmp_path, source):
    store = Store(tmp_path)
    existing = store.import_text('keep.txt', 'Keep this reading.')
    store.bookmark(existing['id'], 2, 0.3)
    with pytest.raises(ValueError, match='readable'):
        store.import_text('bad.md', source)
    assert store.recent()[0]['id'] == existing['id']
    assert len(store.recent()) == 1
    assert store.document(existing['id'])['bookmark'] == {'word': 2, 'offset': 0.3}


def test_incomplete_markup_unicode_and_literal_punctuation_survive():
    text = markdown_to_text('# “Hello” 😀\n\n**unfinished emphasis\n\nPrice: $3.50. C++ and x < y.\n\n[unclosed link')
    assert '“Hello” 😀' in text
    assert 'unfinished emphasis' in text and '[unclosed link' in text
    assert '$3.50' in text and 'C++' in text and 'x < y' in text
    assert 'Keep the story' in markdown_to_text('---\n\nKeep the story\n\n---')


def test_native_markdown_reload_utf16_and_bad_input(tmp_path):
    store = Store(tmp_path / 'data')
    path = tmp_path / 'reading.MD'
    path.write_text('# First\n\n**one** two three.', encoding='utf-16')
    doc = store.open_path(path)
    store.bookmark(doc['id'], 3, 0.25)
    assert store.reload(doc['id'])['bookmark']['word'] == 3
    path.write_text('# Second\n\n*Changed* words.', encoding='utf-8')
    changed = store.reload(doc['id'])
    assert changed['id'] != doc['id'] and changed['bookmark']['word'] == 0
    assert '*' not in changed['text']
    path.write_bytes(b'\xff\xfe\x01')
    with pytest.raises(ValueError, match='decoded'):
        store.open_path(path)
    with pytest.raises(ValueError, match='binary'):
        store.import_text('binary.md', '# Text\x00garbage')
    with pytest.raises(ValueError, match='5 MB'):
        store.import_text('large.md', 'a' * 5_000_001)
    with pytest.raises(ValueError, match='Markdown'):
        store.open_path(tmp_path / 'bad.html')


def test_existing_database_migration_and_highlighting_settings(tmp_path):
    db = sqlite3.connect(tmp_path / 'library.sqlite3')
    db.executescript('''CREATE TABLE documents (id TEXT PRIMARY KEY, name TEXT NOT NULL,
        text TEXT NOT NULL, source TEXT, updated REAL NOT NULL,
        word INTEGER NOT NULL DEFAULT 0, offset REAL NOT NULL DEFAULT 0);
        CREATE TABLE settings (id INTEGER PRIMARY KEY, value TEXT NOT NULL);
        INSERT INTO documents VALUES ('old', 'old.txt', 'Old words.', NULL, 1, 1, 0.2);''')
    db.execute('INSERT INTO settings VALUES (1,?)', (json.dumps({'wordHighlight': True, 'dimSurrounding': True}),))
    db.commit()
    db.close()
    store = Store(tmp_path)
    assert store.document('old')['format'] == 'text'
    assert store.document('old')['bookmark']['word'] == 1
    assert store.recent()[0]['id'] == 'old'
    store.remove_recent('old')
    assert Store(tmp_path).recent() == []
    assert store.document('old')['bookmark']['word'] == 1
    assert store.settings()['highlightMode'] == 'sentence'
    for mode in ('line', 'sentence'):
        result = store.save_settings({'highlightMode': mode})
        assert result['highlightMode'] == mode
        assert result['wordHighlight'] and result['dimSurrounding']
    for bad in ('paragraph', None, True, ['line']):
        with pytest.raises(ValueError, match='highlighting'):
            store.save_settings({'highlightMode': bad})
    assert Store(tmp_path).settings()['highlightMode'] == 'sentence'
