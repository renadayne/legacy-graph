"""Unit checks for mfcgraph_core/explore_windows.py.

Run:  python3 tests/test_explore_windows.py
"""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))

from mfcgraph_core.explore_windows import windows_for, render, signature_only  # noqa: E402

passed = 0
failed = 0


def check(ok, what, detail=""):
    global passed, failed
    if ok:
        passed += 1
        return
    failed += 1
    print("FAIL: " + what + ("\n  " + repr(detail) if detail else ""))


def main():
    # focus in the middle of a long function: signature, window, closing brace
    w = windows_for((10, 100), [50], 200)
    check(w == [(10, 10), (44, 56), (100, 100)], "window +-6 with signature and closing line", w)
    # near the signature: merged with it (gap <= 3)
    w = windows_for((10, 100), [19], 200)
    check(w == [(10, 25), (100, 100)], "merge with signature when gap <= 3", w)
    # two focus lines close together merge
    w = windows_for((1, 200), [50, 64], 200)
    check(w == [(1, 1), (44, 70), (200, 200)], "merge nearby windows", w)
    w = windows_for((1, 200), [50, 66], 200)
    check(w == [(1, 1), (44, 72), (200, 200)], "gap of 3 lines merges", w)
    w = windows_for((1, 200), [50, 67], 200)
    check(w == [(1, 1), (44, 56), (61, 73), (200, 200)], "gap of 4 lines does not merge", w)
    # focus outside the span ignored; no focus -> whole function if it fits
    w = windows_for((5, 20), [100], 50)
    check(w == [(5, 20)], "no focus inside -> whole small function", w)
    w = windows_for((1, 100), [], 10)
    check(w == [(1, 9), (100, 100)], "no focus, long function -> head + closing", w)
    # max_lines forces radius shrink, then dropping later focus lines
    w = windows_for((1, 100), [30, 70], 12)
    check(sum(e - s + 1 for s, e in w) <= 12 and (28, 32) in w, "radius shrinks to fit", w)
    w = windows_for((1, 100), [20, 40, 60, 80], 5)
    check(sum(e - s + 1 for s, e in w) <= 5 and (20, 20) in w, "later focus dropped when too long", w)

    lines = ["line%d" % i for i in range(1, 31)]
    lines[9] = "void CFoo::Bar(int a,"
    lines[10] = "               int b) {"
    out = render(lines, [(10, 12), (20, 21)], "Foo.cpp")
    want = ("10\tvoid CFoo::Bar(int a,\n11\t               int b) {\n12\tline12\n"
            "… lines 13-19 elided — mfc_explore \"Foo.cpp:13-19\" returns them\n20\tline20\n21\tline21")
    check(out == want, "render with elision marker", out)
    out = render(lines, [(1, 1), (3, 3)], "a.cpp")
    check("… line 2 elided — mfc_explore \"a.cpp:2\" returns it" in out, "single-line elision", out)
    sig = signature_only(lines, (10, 30))
    check(sig == "10\tvoid CFoo::Bar(int a,\n11\t               int b)", "signature only (multi-line)", sig)
    lines2 = ["BOOL CDoc::Save()", "{", "  return TRUE;", "}"]
    check(signature_only(lines2, (1, 4)) == "1\tBOOL CDoc::Save()", "signature only, brace on next line",
          signature_only(lines2, (1, 4)))
    print("explore_windows: %d passed, %d failed" % (passed, failed))
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
