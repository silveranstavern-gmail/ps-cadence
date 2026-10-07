from __future__ import annotations

import hashlib
import json
import math
import sqlite3
import threading
import time
from pathlib import Path

from .text import parse_text
from .markdown import markdown_to_text

VOICES = {
    'bm_lewis': 'Lewis · British', 'am_michael': 'Michael · American',
    'af_heart': 'Heart · American', 'bf_emma': 'Emma · British',
    'am_adam': 'Adam · American', 'bf_isabella': 'Isabella · British',
}
DEFAULTS = {'voice': 'bm_lewis', 'rate': 1.0, 'fontSize': 23, 'lineHeight': 1.85,
            'follow': True, 'wordHighlight': False, 'dimSurrounding': False, 'highlightMode': 'sentence', 'volume': 1.0}


class Store:
    def __init__(self, directory: Path):
        directory = directory.resolve()
        self.directory = directory
        directory.mkdir(parents=True, exist_ok=True)
        self.lock = threading.RLock()
        self.parsed = {}
        self.db = sqlite3.connect(directory / 'library.sqlite3', check_same_thread=False)
        self.db.row_factory = sqlite3.Row
        self.db.executescript('''
            CREATE TABLE IF NOT EXISTS documents (
                id TEXT PRIMARY KEY, name TEXT NOT NULL, text TEXT NOT NULL, source TEXT,
                updated REAL NOT NULL, word INTEGER NOT NULL DEFAULT 0, offset REAL NOT NULL DEFAULT 0
            );
            CREATE TABLE IF NOT EXISTS settings (id INTEGER PRIMARY KEY, value TEXT NOT NULL);
        ''')
        if 'format' not in {row['name'] for row in self.db.execute('PRAGMA table_info(documents)')}:
            self.db.execute("ALTER TABLE documents ADD COLUMN format TEXT NOT NULL DEFAULT 'text'")
        if 'recent_hidden' not in {row['name'] for row in self.db.execute('PRAGMA table_info(documents)')}:
            self.db.execute('ALTER TABLE documents ADD COLUMN recent_hidden INTEGER NOT NULL DEFAULT 0')
        self.db.commit()

    def import_text(self, name: str, text: str, source: str | None = None) -> dict:
        if not isinstance(text, str) or len(text.encode('utf-8')) > 5_000_000:
            raise ValueError('Please select text smaller than 5 MB.')
        if '\x00' in text:
            raise ValueError('This looks like a binary file. Please select a .txt or .md text file.')
        source_format = 'markdown' if Path(name).suffix.lower() == '.md' else 'text'
        if source_format == 'markdown':
            text = markdown_to_text(text)
        parsed = parse_text(text)
        doc_id = hashlib.sha256(parsed['text'].encode('utf-8')).hexdigest()[:24]
        name = Path(name).name[:200] or 'Untitled text'
        with self.lock:
            self.db.execute('''INSERT INTO documents (id,name,text,source,updated,format) VALUES (?,?,?,?,?,?)
                ON CONFLICT(id) DO UPDATE SET name=excluded.name,
                source=COALESCE(excluded.source,documents.source),updated=excluded.updated,format=excluded.format,recent_hidden=0''',
                (doc_id, name, parsed['text'], source, time.time(), source_format))
            self.db.commit()
            self.parsed[doc_id] = parsed
        return self.document(doc_id)

    def open_path(self, path: str | Path) -> dict:
        path = Path(path).resolve()
        if path.suffix.lower() not in ('.txt', '.md'):
            raise ValueError('Please select a text (.txt) or Markdown (.md) file.')
        if path.stat().st_size > 5_000_000:
            raise ValueError('Please select a text file smaller than 5 MB.')
        data = path.read_bytes()
        try:
            if data.startswith((b'\xff\xfe', b'\xfe\xff')):
                text = data.decode('utf-16')
            else:
                try:
                    text = data.decode('utf-8-sig')
                except UnicodeDecodeError:
                    text = data.decode('cp1252')
        except UnicodeDecodeError as error:
            raise ValueError('This file could not be decoded. Save it as UTF-8 text and try again.') from error
        return self.import_text(path.name, text, str(path))

    def document(self, doc_id: str) -> dict:
        with self.lock:
            row = self.db.execute('SELECT * FROM documents WHERE id=?', (doc_id,)).fetchone()
            if row is None:
                raise KeyError(doc_id)
            if doc_id not in self.parsed:
                self.parsed[doc_id] = parse_text(row['text'])
            parsed = self.parsed[doc_id]
        return {'id': row['id'], 'name': row['name'], 'format': row['format'], 'reloadable': bool(row['source']),
                'bookmark': {'word': min(row['word'], len(parsed['words']) - 1), 'offset': row['offset']}, **parsed}

    def reload(self, doc_id: str) -> dict:
        with self.lock:
            row = self.db.execute('SELECT source FROM documents WHERE id=?', (doc_id,)).fetchone()
        if not row or not row['source']:
            raise ValueError('Choose the file again to refresh this text.')
        return self.open_path(row['source'])

    def recent(self, limit: int | None = 20) -> list[dict]:
        with self.lock:
            query = 'SELECT id,name,word,updated,substr(text,1,240) AS preview FROM documents WHERE recent_hidden=0 ORDER BY updated DESC'
            rows = self.db.execute(query + (' LIMIT ?' if limit is not None else ''),
                                   (limit,) if limit is not None else ()).fetchall()
        return [dict(r) for r in rows]

    def remove_recent(self, doc_id: str):
        with self.lock:
            result = self.db.execute('UPDATE documents SET recent_hidden=1 WHERE id=?', (doc_id,))
            self.db.commit()
            if not result.rowcount:
                raise KeyError(doc_id)

    def clear_recent(self):
        with self.lock:
            self.db.execute('UPDATE documents SET recent_hidden=1')
            self.db.commit()

    def bookmark(self, doc_id: str, word: int, offset: float):
        document = self.document(doc_id)
        word = max(0, min(int(word), len(document['words']) - 1))
        if not math.isfinite(offset):
            raise ValueError('Invalid reading position.')
        with self.lock:
            self.db.execute('UPDATE documents SET word=?,offset=?,updated=? WHERE id=?',
                            (word, max(0, min(offset, 3600)), time.time(), doc_id))
            self.db.commit()

    def settings(self) -> dict:
        with self.lock:
            row = self.db.execute('SELECT value FROM settings WHERE id=1').fetchone()
        return {**DEFAULTS, **(json.loads(row[0]) if row else {})}

    def save_settings(self, changes: dict) -> dict:
        settings = self.settings()
        if 'voice' in changes:
            if changes['voice'] not in VOICES:
                raise ValueError('Unknown voice.')
            settings['voice'] = changes['voice']
        for key, lower, upper in [('rate', 0.5, 2.5), ('fontSize', 16, 36), ('lineHeight', 1.3, 2.4), ('volume', 0, 1)]:
            if key in changes:
                value = float(changes[key])
                if not math.isfinite(value):
                    raise ValueError('Invalid setting.')
                settings[key] = max(lower, min(upper, value))
        if 'follow' in changes:
            settings['follow'] = bool(changes['follow'])
        for key in ('wordHighlight', 'dimSurrounding'):
            if key in changes:
                if not isinstance(changes[key], bool):
                    raise ValueError('Invalid setting.')
                settings[key] = changes[key]
        if 'highlightMode' in changes:
            if changes['highlightMode'] not in ('sentence', 'line'):
                raise ValueError('Choose sentence or line highlighting.')
            settings['highlightMode'] = changes['highlightMode']
        with self.lock:
            self.db.execute('INSERT OR REPLACE INTO settings (id,value) VALUES (1,?)', (json.dumps(settings),))
            self.db.commit()
        return settings
