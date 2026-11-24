"""Optional desktop GUI for mfcgraph (tkinter, Python standard library only).

Started only by `python mfcgraph.py gui`; nothing in mfcgraph_core imports this package elsewhere, so the command line
and the MCP server work even when tkinter is missing or this folder is removed.
    logic.py  everything testable without a display (no tkinter import)
    app.py    the tkinter window
    guide.py  the built-in user guide (Vietnamese)
"""
