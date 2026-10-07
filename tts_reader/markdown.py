"""Convert Markdown to a single safe display/speech text, never to executable HTML."""
from __future__ import annotations

import re
from html import escape
from html.parser import HTMLParser

from markdown_it import MarkdownIt


class _ReadableHTML(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.parts = []
        self.hidden = []

    def handle_starttag(self, tag, attrs):
        if tag in ('script', 'style', 'template', 'iframe', 'object', 'pre'):
            self.hidden.append(tag)
        elif not self.hidden:
            if tag in ('br', 'p', 'div', 'li', 'tr', 'h1', 'h2', 'h3', 'h4', 'h5', 'h6'):
                self.parts.append('\n')
            elif tag == 'img':
                self.parts.append(dict(attrs).get('alt') or '')

    def handle_endtag(self, tag):
        if tag in self.hidden:
            # Recover from mismatched nesting without exposing hidden content.
            del self.hidden[self.hidden.index(tag):]
        elif not self.hidden and tag in ('p', 'div', 'li', 'tr', 'h1', 'h2', 'h3', 'h4', 'h5', 'h6'):
            self.parts.append('\n')

    def handle_data(self, data):
        if not self.hidden:
            self.parts.append(data)


def markdown_to_text(source: str) -> str:
    source = source.lstrip('\ufeff').replace('\r\n', '\n').replace('\r', '\n')
    # Remove only a closed front matter block at the beginning of a document.
    lines = source.split('\n')
    if lines[0].strip() == '---':
        for n, line in enumerate(lines[1:201], 1):
            if line.strip() in ('---', '...'):
                if any(re.match(r'^\s*[\w-]+\s*:', entry) for entry in lines[1:n]):
                    source = '\n'.join(lines[n + 1:])
                break
    parser = MarkdownIt('commonmark', {'maxNesting': 40}).enable(['table', 'strikethrough'])
    output = _ReadableHTML()

    def inline(tokens):
        for token in tokens:
            if token.type in ('text', 'code_inline'):
                output.feed(escape(token.content))
            elif token.type in ('softbreak', 'hardbreak'):
                output.feed('\n')
            elif token.type == 'html_inline':
                output.feed(token.content)
            elif token.type == 'image':
                inline(token.children or [])

    list_item_start = False
    in_row = False
    for token in parser.parse(source):
        if token.type == 'list_item_open':
            list_item_start = True
        elif token.type == 'inline':
            children = token.children or []
            # Task list checkboxes are metadata, not words to pronounce.
            if list_item_start and children and children[0].type == 'text':
                children[0].content = re.sub(r'^\[[ xX]\]\s+', '', children[0].content)
            list_item_start = False
            inline(children)
        elif token.type == 'html_block':
            output.feed(token.content)
            output.feed('\n\n')
        elif token.type == 'tr_open':
            in_row = True
        elif token.type in ('td_close', 'th_close'):
            output.feed('. ')
        elif token.type == 'tr_close':
            in_row = False
            output.feed('\n\n')
        elif token.type in ('paragraph_close', 'heading_close', 'list_item_close', 'blockquote_close', 'hr') and not in_row:
            output.feed('\n\n')
        # Fence and indented code tokens are deliberately omitted.
    output.close()
    text = ''.join(output.parts)
    text = re.sub(r'[ \t]+\n', '\n', text)
    return re.sub(r'\n{3,}', '\n\n', text).strip()
