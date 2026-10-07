"""Read Unicode clipboard text in the Windows desktop app, without another dependency."""
import ctypes
from ctypes import wintypes


def read_text() -> str:
    user32 = ctypes.WinDLL('user32', use_last_error=True)
    kernel32 = ctypes.WinDLL('kernel32', use_last_error=True)
    user32.IsClipboardFormatAvailable.argtypes = [wintypes.UINT]
    user32.IsClipboardFormatAvailable.restype = wintypes.BOOL
    user32.OpenClipboard.argtypes = [wintypes.HWND]
    user32.OpenClipboard.restype = wintypes.BOOL
    user32.GetClipboardData.argtypes = [wintypes.UINT]
    user32.GetClipboardData.restype = wintypes.HANDLE
    user32.CloseClipboard.argtypes = []
    user32.CloseClipboard.restype = wintypes.BOOL
    kernel32.GlobalLock.argtypes = [wintypes.HGLOBAL]
    kernel32.GlobalLock.restype = ctypes.c_void_p
    kernel32.GlobalUnlock.argtypes = [wintypes.HGLOBAL]
    kernel32.GlobalUnlock.restype = wintypes.BOOL
    kernel32.GlobalSize.argtypes = [wintypes.HGLOBAL]
    kernel32.GlobalSize.restype = ctypes.c_size_t
    if not user32.OpenClipboard(None):
        raise ValueError('The clipboard is busy. Try again in a moment.')
    try:
        if not user32.IsClipboardFormatAvailable(13):  # CF_UNICODETEXT
            return ''
        handle = user32.GetClipboardData(13)
        if not handle:
            raise ValueError('Could not read clipboard text. Copy the text again and retry.')
        size = kernel32.GlobalSize(handle)
        if size > 10_000_002:
            raise ValueError('Please copy text smaller than 5 MB.')
        pointer = kernel32.GlobalLock(handle)
        if not pointer:
            raise ValueError('Could not read clipboard text. Copy the text again and retry.')
        try:
            return ctypes.string_at(pointer, size).decode('utf-16-le').split('\0', 1)[0]
        finally:
            kernel32.GlobalUnlock(handle)
    finally:
        user32.CloseClipboard()
