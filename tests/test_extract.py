"""Extractor unit checks (v0.2 additions) on samples/LegacyApp.

Run:  python3 tests/test_extract.py
"""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, ROOT)

from mfcgraph_core.encoding import decode_bytes  # noqa: E402
from mfcgraph_core.extract_cpp import extract_cpp, clean_literal  # noqa: E402
from mfcgraph_core.lexer import lex, filter_conditionals  # noqa: E402
from mfcgraph_core.model import RawData  # noqa: E402

SAMPLES = os.path.join(ROOT, "samples", "LegacyApp")
passed = 0
failed = 0


def check(ok, what, detail=""):
    global passed, failed
    if ok:
        passed += 1
        return
    failed += 1
    print("FAIL: " + what + ("\n  " + str(detail) if detail else ""))


def extract_text(text):
    raw = RawData()
    active, _ = filter_conditionals(lex(text, False))
    extract_cpp(active, 0, raw)
    return raw


def extract_file(rel):
    with open(os.path.join(SAMPLES, rel), "rb") as fh:
        text, _ = decode_bytes(fh.read(), 1258)
    return extract_text(text)


def func(raw, cls, name):
    for f in raw.funcs:
        if f.is_def and f.cls == cls and f.name == name:
            return f
    return None


def test_strings():
    f = func(extract_file("MainFrm.cpp"), "CMainFrame", "OnFileExport")
    check(f is not None and (69, "Export failed") in f.strings, "S2a: 'Export failed' at line 69 (PLAN says 68; file has 69)",
          f and f.strings)
    check(clean_literal("%d") == "" and clean_literal("\\r\\n") == "" and clean_literal("%s: %d") == "",
          "S2a: format-only strings dropped")
    check(clean_literal("ab") == "" and clean_literal("abc") == "abc", "S2a: < 3 letters dropped")
    check(len(clean_literal("x" * 500)) == 200, "S2a: cut at 200 chars")
    check(clean_literal("Không thể lưu") == "Không thể lưu", "S2a: Vietnamese kept")
    raw = extract_text('void F()\n{\n  Show(_T("abc " "def"),\n   "%d");\n  x = "ghi\\tjkl";\n}\n')
    f = func(raw, "", "F")
    check(f is not None and f.strings == [(3, "abc def"), (5, "ghi\\tjkl")], "S2a: adjacent literals joined",
          f and f.strings)


def main():
    test_strings()
    print("extract: %d passed, %d failed" % (passed, failed))
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
