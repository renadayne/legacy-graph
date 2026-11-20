"""Run every test suite in tests/ (each is a standalone script). Exit code 1 if any fails.

Run:  python3 tests/run_all.py
"""
import os
import runpy
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
SUITES = ["test_mfcgraph.py", "golden_test.py", "test_extract.py", "test_index.py", "test_explore_query.py",
          "test_explore_seed.py", "test_explore_windows.py", "test_explore.py", "test_pp.py", "test_win32.py",
          "eval_explore.py", ("eval_explore.py", "--win32")]


def main():
    bad = []
    for item in SUITES:
        name, args = (item[0], list(item[1:])) if isinstance(item, tuple) else (item, [])
        path = os.path.join(HERE, name)
        if not os.path.exists(path):
            continue
        saved = sys.argv
        sys.argv = [path] + args
        try:
            runpy.run_path(path, run_name="__main__")
            code = 0
        except SystemExit as ex:
            code = ex.code or 0
        finally:
            sys.argv = saved
        if code:
            bad.append(" ".join([name] + args))
    print("ALL: %s" % ("OK" if not bad else "FAILED: " + ", ".join(bad)))
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
