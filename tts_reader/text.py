"""Stable display words and bounded synthesis passages share the same word IDs."""
from __future__ import annotations

import re
import unicodedata

SENTENCE_END = re.compile(r'[.!?…][\"\u201d\u2019\)\]]*$')


def parse_text(text: str, max_chars: int = 380) -> dict:
    text = unicodedata.normalize('NFC', text.lstrip('\ufeff').replace('\r\n', '\n').replace('\r', '\n'))
    text = re.sub(r'[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]', '', text)
    words, paragraphs = [], []
    sentence = 0
    for paragraph in re.split(r'\n\s*\n', text):
        if not paragraph.strip() or paragraph.strip() == '===':
            continue
        ids = []
        matches = list(re.finditer(r'\S+', paragraph))
        for n, match in enumerate(matches):
            word_id = len(words)
            ids.append(word_id)
            end = matches[n + 1].start() if n + 1 < len(matches) else len(paragraph)
            words.append({'id': word_id, 'text': match.group(), 'after': paragraph[match.end():end],
                          'sentence': sentence, 'paragraph': len(paragraphs)})
            if SENTENCE_END.search(match.group()):
                sentence += 1
        if ids:
            paragraphs.append(ids)
            if words[-1]['sentence'] == sentence:
                sentence += 1
    if not words:
        raise ValueError('This file has no readable text.')
    if len(words) > 100_000:
        raise ValueError('Please open shorter text (at most 100,000 words).')
    chunks = []
    start = 0
    while start < len(words):
        end, size, boundary = start, 0, None
        while end < len(words):
            addition = len(words[end]['text']) + (1 if end > start else 0)
            if end > start and size + addition > max_chars:
                break
            size += addition
            end += 1
            if end == len(words) or words[end - 1]['sentence'] != words[end]['sentence']:
                boundary = end
        # Prefer sentence boundaries without turning a large passage into a tiny one.
        if end < len(words) and boundary and boundary > start and boundary - start >= (end - start) / 2:
            end = boundary
        local_words, cursor = [], 0
        for word in words[start:end]:
            local_words.append({'start': cursor, 'end': cursor + len(word['text'])})
            cursor += len(word['text']) + 1
        chunks.append({'index': len(chunks), 'word_start': start, 'word_end': end,
                       'text': ' '.join(w['text'] for w in words[start:end]), 'local_words': local_words})
        start = end
    return {'text': text, 'words': words, 'paragraphs': paragraphs, 'chunks': chunks}


def align_tokens(local_words: list[dict], token_spans: list[dict], duration: float) -> list[dict]:
    """Aggregate phonemizer subtokens onto original visible words, including numbers.

    Unspoken punctuation seeks to the nearest spoken boundary. Approximate timings
    are explicitly flagged; equal-duration guessing is never used for spoken text.
    """
    timings = []
    for n, word in enumerate(local_words):
        spans = [t for t in token_spans if t['char_start'] < word['end'] and t['char_end'] > word['start']]
        if spans:
            timings.append({'local_word': n, 'start': max(0.0, min(t['start'] for t in spans)),
                            'end': min(duration, max(t['end'] for t in spans)), 'approximate': False})
        else:
            timings.append({'local_word': n, 'start': None, 'end': None, 'approximate': True})
    for n, timing in enumerate(timings):
        if timing['start'] is not None:
            continue
        following = next((t['start'] for t in timings[n + 1:] if t['start'] is not None), None)
        preceding = next((t['end'] for t in reversed(timings[:n]) if t['end'] is not None), 0.0)
        timing['start'] = timing['end'] = following if following is not None else preceding
    for timing in timings:
        timing['start'] = round(min(duration, timing['start']), 4)
        timing['end'] = round(max(timing['start'], timing['end']), 4)
    return timings
