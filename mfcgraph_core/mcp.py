"""Model Context Protocol server over stdio (newline-delimited JSON-RPC 2.0).

No sockets, no network: the IDE starts this process and talks through
stdin/stdout. Only runs when the user starts `mfcgraph serve`.
"""
import json
import sys

from . import VERSION
from .index import load_graph
from .query import (q_search, q_node, q_callers, q_callees, q_impact, q_trace, q_msgmap, q_context,
                    q_status)

MAX_TOOL_OUTPUT = 16000  # characters; keeps agent context small


def _obj(props, required=()):
    d = {"type": "object", "properties": props}
    if required:
        d["required"] = list(required)
    return d


_S = {"type": "string"}
_I = {"type": "integer"}
_B = {"type": "boolean"}

TOOLS = [
    ("mfc_search", "Find classes, functions, command/resource IDs, menu captions and dialog captions by (part of) "
                   "name. Use this first when you only know a word.",
     _obj({"query": _S, "limit": _I}, ["query"])),
    ("mfc_node", "Show one symbol: location, signature, flags (framework entry, message handler), UI triggers, "
                 "caller/callee counts and its source code.",
     _obj({"symbol": dict(_S, description="Class, Class::Method or function"), "code": _B,
           "max_code_lines": _I}, ["symbol"])),
    ("mfc_callers", "Who calls this function, including MFC message-map routing up to menu items / accelerators / "
                    "toolbar buttons.", _obj({"symbol": _S, "depth": _I}, ["symbol"])),
    ("mfc_callees", "What this function calls (tree). External MFC/Win32 calls are summarised on one line.",
     _obj({"symbol": _S, "depth": _I}, ["symbol"])),
    ("mfc_impact", "Blast radius of changing a function: affected functions, UI entry points and files.",
     _obj({"symbol": _S, "depth": _I}, ["symbol"])),
    ("mfc_trace", "Trace a UI action to code: menu caption (e.g. 'Export'), accelerator, command ID "
                  "(ID_FILE_EXPORT) or dialog ID (IDD_EXPORT) -> message-map handler -> what it calls. For dialogs: "
                  "controls, DDX members, handlers.", _obj({"query": _S, "depth": _I}, ["query"])),
    ("mfc_context", "Compact context pack for a symbol (code + callers + callees + UI triggers) in Markdown. "
                    "Prefer this over reading whole files.",
     _obj({"symbol": _S, "max_code_lines": _I}, ["symbol"])),
    ("mfc_msgmap", "List the MFC message map of a class (macro, ID/message, handler, location).",
     _obj({"class": _S}, ["class"])),
    ("mfc_status", "Index status: root, creation time, counts.", _obj({})),
]

INSTRUCTIONS = ("Offline code graph of a C++/MFC codebase. Start with mfc_search or mfc_trace (menu caption / "
                "command ID / dialog ID), then mfc_context for the symbol you need. Prefer these tools over "
                "reading whole files.")


def _int(a, k, d):
    v = a.get(k, d)
    try:
        return int(v)
    except (TypeError, ValueError):
        return d


def _run_tool(g, index_path, name, a):
    if name == "mfc_search":
        return q_search(g, str(a.get("query", "")), _int(a, "limit", 30)), False
    if name == "mfc_node":
        return q_node(g, str(a.get("symbol", "")), bool(a.get("code", True)), _int(a, "max_code_lines", 80)), False
    if name == "mfc_callers":
        return q_callers(g, str(a.get("symbol", "")), _int(a, "depth", 5)), False
    if name == "mfc_callees":
        return q_callees(g, str(a.get("symbol", "")), _int(a, "depth", 2)), False
    if name == "mfc_impact":
        return q_impact(g, str(a.get("symbol", "")), _int(a, "depth", 5)), False
    if name == "mfc_trace":
        return q_trace(g, str(a.get("query", "")), _int(a, "depth", 2)), False
    if name == "mfc_context":
        return q_context(g, str(a.get("symbol", "")), _int(a, "max_code_lines", 80)), False
    if name == "mfc_msgmap":
        return q_msgmap(g, str(a.get("class", ""))), False
    if name == "mfc_status":
        return q_status(g, index_path), False
    return "unknown tool: " + name, True


def _clamp(s):
    if len(s) <= MAX_TOOL_OUTPUT:
        return s
    return s[:MAX_TOOL_OUTPUT] + "\n... (output truncated; narrow the query)\n"


def run_mcp_server(index_path):
    out = sys.stdout.buffer

    def send(obj):
        out.write(json.dumps(obj, ensure_ascii=False).encode("utf-8") + b"\n")
        out.flush()

    try:
        g = load_graph(index_path)
        err = ""
    except ValueError as ex:
        g = None
        err = str(ex)
        sys.stderr.write("mfcgraph: %s\n" % err)  # stderr is shown in the IDE's MCP log

    for raw in sys.stdin.buffer:
        line = raw.decode("utf-8", "replace").strip()
        if not line:
            continue
        try:
            req = json.loads(line)
            if not isinstance(req, dict):
                raise ValueError("not an object")
        except ValueError as ex:
            send({"jsonrpc": "2.0", "id": None, "error": {"code": -32700, "message": "parse error: %s" % ex}})
            continue
        if "id" not in req:
            continue  # notification
        rid = req.get("id")
        method = req.get("method", "")
        params = req.get("params") or {}
        if method == "initialize":
            result = {"protocolVersion": params.get("protocolVersion", "2025-06-18"),
                      "capabilities": {"tools": {"listChanged": False}},
                      "serverInfo": {"name": "mfcgraph", "version": VERSION},
                      "instructions": INSTRUCTIONS}
        elif method == "ping":
            result = {}
        elif method == "tools/list":
            result = {"tools": [{"name": n, "description": d, "inputSchema": s} for n, d, s in TOOLS]}
        elif method == "tools/call":
            name = params.get("name", "")
            args = params.get("arguments") or {}
            if g is None:
                text, is_error = "Index not available: " + err, True
            else:
                try:
                    text, is_error = _run_tool(g, index_path, name, args)
                except Exception as ex:  # never crash the server on one bad query
                    text, is_error = "internal error: %s" % ex, True
            result = {"content": [{"type": "text", "text": _clamp(text)}], "isError": is_error}
        elif method == "resources/list":
            result = {"resources": []}
        elif method == "prompts/list":
            result = {"prompts": []}
        else:
            send({"jsonrpc": "2.0", "id": rid, "error": {"code": -32601, "message": "method not found: " + method}})
            continue
        send({"jsonrpc": "2.0", "id": rid, "result": result})
    return 0
