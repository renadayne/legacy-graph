"""Detect source-file encoding and decode to str.

Handles UTF-8 (with/without BOM), UTF-16 LE/BE (typical for .rc files) and
legacy ANSI code pages such as 1258 (Vietnamese) or 932 (Japanese).
"""
import unicodedata


def _looks_utf16le(b):
    if len(b) < 8:
        return False
    sample = b[:4096]
    n = len(sample) - (len(sample) % 2)
    zeros_even = sample[0:n:2].count(0)
    zeros_odd = sample[1:n:2].count(0)
    return zeros_odd > len(sample) // 4 and zeros_even < len(sample) // 50


def _ansi(b, cp):
    try:
        s = b.decode("cp%d" % cp, "replace")
    except LookupError:
        s = b.decode("latin-1")
    # CP1258 stores Vietnamese tone marks as combining characters; compose them (NFC)
    # so that searching for "nhập" matches regardless of how the file was saved.
    return unicodedata.normalize("NFC", s)


def decode_bytes(b, codepage):
    """Returns (text, encoding_label)."""
    if b.startswith(b"\xef\xbb\xbf"):
        return b[3:].decode("utf-8", "replace"), "utf8-bom"
    if b.startswith(b"\xff\xfe"):
        return b[2:].decode("utf-16-le", "replace"), "utf16le"
    if b.startswith(b"\xfe\xff"):
        return b[2:].decode("utf-16-be", "replace"), "utf16be"
    if _looks_utf16le(b):
        return b.decode("utf-16-le", "replace"), "utf16le"
    try:
        s = b.decode("utf-8")
        return s, ("ascii" if s.isascii() else "utf8")
    except UnicodeDecodeError:
        pass
    return _ansi(b, codepage), "ansi:%d" % codepage


def decode_with_label(b, label, fallback_cp):
    """Re-decode using a previously detected label (for code snippets)."""
    if label.startswith("ansi:"):
        try:
            cp = int(label[5:])
        except ValueError:
            cp = fallback_cp
        return _ansi(b, cp or fallback_cp)
    return decode_bytes(b, fallback_cp)[0]
