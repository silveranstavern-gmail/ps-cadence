import ctypes
from types import SimpleNamespace

import pytest

from tts_reader.clipboard import read_text


@pytest.mark.parametrize('available', [True, False])
def test_unicode_and_nontext_clipboard(monkeypatch, available):
    # A real UTF-16 buffer exercises Unicode decoding and pointer-sized handles.
    text = 'Mira said, “Hello!”\r\n\r\nA lantern glowed. 😀'
    payload = (text + '\0').encode('utf-16-le')
    memory = ctypes.create_string_buffer(payload)
    handle = 0x123456789
    calls = []

    def get_data(_):
        return handle

    def lock(value):
        assert value == handle
        return ctypes.addressof(memory)

    def unlock(value):
        assert value == handle
        calls.append('unlock')
        return True

    def close():
        calls.append('close')
        return True

    user32 = SimpleNamespace(OpenClipboard=lambda _: True,
        IsClipboardFormatAvailable=lambda _: available, GetClipboardData=get_data,
        CloseClipboard=close)
    kernel32 = SimpleNamespace(GlobalLock=lock, GlobalUnlock=unlock,
        GlobalSize=lambda _: len(payload))
    monkeypatch.setattr(ctypes, 'WinDLL', lambda name, **_: user32 if name == 'user32' else kernel32,
                        raising=False)
    assert read_text() == (text if available else '')
    assert calls == (['unlock', 'close'] if available else ['close'])
