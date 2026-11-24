"""Create or update the mfcgraph entry of an IDE MCP config file (.mcp.json / .vscode/mcp.json).

Only runs when the user asks for it (`mcp-config --write FILE` or the GUI's own button). It never touches other
servers or keys, keeps a backup FILE.bak of the previous content, and refuses files that are not plain JSON
(e.g. with comments) instead of rewriting them. Not imported by `serve` or any query command.

Interface:
    server_entry(root, launcher=None, python=None, tools="explore") -> dict
        {"type": "stdio", "command": python, "args": [launcher, "serve", "--root", root],
         "env": {"MFCGRAPH_MCP_TOOLS": tools}}   defaults: this tool's mfcgraph.py and the running python
    snippet(name, entry) -> str                  {"servers": {name: entry}} as text (to paste by hand)
    merge(text, name, entry) -> (new_text, action)   action "added" | "updated" | "unchanged"; ValueError if
                                                     text is not a JSON object / "servers" is not an object
    write(path, name, entry) -> (action, backup_path | None)   atomic replace; no write when unchanged
    suggest_targets(root) -> [(label, path)]     Visual Studio (<root>/.mcp.json) and VS Code (<root>/.vscode/mcp.json)
Both IDEs use the same {"servers": {...}} format.
"""
import io
import json
import os
import shutil
import sys

DEFAULT_NAME = "mfcgraph"


def default_launcher():
    return os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "mfcgraph.py")


def console_python(exe=None):
    """The console interpreter: a GUI started with pythonw.exe must still register python.exe (stdio server)."""
    exe = exe or sys.executable or "python"
    folder, base = os.path.split(exe)
    if base.lower().startswith("pythonw"):
        alt = os.path.join(folder, "python" + base[len("pythonw"):])
        if os.path.isfile(alt):
            return alt
    return exe


def server_entry(root, launcher=None, python=None, tools="explore"):
    return {"type": "stdio",
            "command": python or console_python(),
            "args": [os.path.abspath(launcher or default_launcher()), "serve", "--root", os.path.abspath(root)],
            "env": {"MFCGRAPH_MCP_TOOLS": tools or "explore"}}


def _dump(obj):
    return json.dumps(obj, indent=2, ensure_ascii=False) + "\n"


def snippet(name, entry):
    return _dump({"servers": {name: entry}})


def merge(text, name, entry):
    if text is None or not text.strip():
        return _dump({"servers": {name: entry}}), "added"
    try:
        data = json.loads(text)
    except ValueError as ex:
        raise ValueError("the file is not plain JSON (comments or trailing commas?): %s. "
                         "Nothing was changed; add the entry by hand (mfcgraph mcp-config prints it)." % ex)
    if not isinstance(data, dict):
        raise ValueError("the file does not hold a JSON object; nothing was changed")
    servers = data.get("servers")
    if servers is None:
        servers = data["servers"] = {}
    if not isinstance(servers, dict):
        raise ValueError('"servers" is not a JSON object; nothing was changed')
    if servers.get(name) == entry:
        return text, "unchanged"
    action = "updated" if name in servers else "added"
    servers[name] = entry
    return _dump(data), action


def write(path, name, entry):
    path = os.path.abspath(path)
    old = None
    if os.path.exists(path):
        with io.open(path, encoding="utf-8-sig") as f:
            old = f.read()
    new, action = merge(old, name, entry)
    if action == "unchanged":
        return action, None
    d = os.path.dirname(path)
    if not os.path.isdir(d):
        os.makedirs(d)
    backup = None
    if old is not None:
        backup = path + ".bak"
        shutil.copyfile(path, backup)
    tmp = path + ".mfcgraph-tmp"
    with io.open(tmp, "w", encoding="utf-8", newline="\n") as f:
        f.write(new)
    os.replace(tmp, path)
    return action, backup


def suggest_targets(root):
    root = os.path.abspath(root)
    return [("Visual Studio 2022 (.mcp.json in the solution folder)", os.path.join(root, ".mcp.json")),
            ("VS Code (.vscode/mcp.json in the workspace)", os.path.join(root, ".vscode", "mcp.json"))]
