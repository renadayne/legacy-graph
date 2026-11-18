"""Lets `python <mfcgraph folder> <command> ...` work the same as `python <folder>/mfcgraph.py <command> ...`.

(Python runs a directory by executing its __main__.py; without this file it fails with
"can't find '__main__' module".)
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from mfcgraph_core.cli import main  # noqa: E402

if __name__ == "__main__":
    sys.exit(main())
