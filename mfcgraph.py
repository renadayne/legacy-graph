#!/usr/bin/env python3
"""mfcgraph launcher. Usage: python mfcgraph.py <command> ...  (see README.md)

Requires only the Python standard library (3.7+). No network access.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from mfcgraph_core.cli import main  # noqa: E402

if __name__ == "__main__":
    sys.exit(main())
