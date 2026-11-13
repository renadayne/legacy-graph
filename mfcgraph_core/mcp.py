"""Model Context Protocol server over stdio (newline-delimited JSON-RPC 2.0).

No sockets, no network: the IDE starts this process and talks through
stdin/stdout. Only runs when the user starts `mfcgraph serve`.
"""
import json
import os
import sys

from . import VERSION
from .index import load_graph
from .query import (q_search, q_node, q_callers, q_callees, q_impact, q_trace, q_msgmap, q_context,
                    q_status, q_refs)
from .explore import explore

MAX_TOOL_OUTPUT = 16000  # characters; keeps agent context small


def _obj(props, required=()):
    d = {"type": "object", "properties": props}
    if required:
        d["required"] = list(required)
    return d


_S = {"type": "string"}
_I = {"type": "integer"}
_B = {"type": "boolean"}

EXPLORE_DESC = (
    "Find the code for a question in ONE call. Returns verbatim line-numbered source of the most relevant "
    "functions (treat it as already read), the call flow between them including MFC hops (menu/accelerator -> "
    "command ID -> message-map handler, PostMessage -> ON_MESSAGE handler), blast radius, and names not shown. "
    "query can be: a bug description in English or Vietnamese; a function/class name; Class::Method; "
    "File.cpp:120 or File.cpp:100-140; a module directory (Billing/); a menu or button caption; an ID "
    "(ID_FILE_EXPORT, IDD_xxx, IDC_xxx, IDS_xxx, WM_APP_xxx); or the exact text of an error message.")

TOOLS = [
    ("mfc_explore", EXPLORE_DESC,
     _obj({"query": dict(_S, description="Question, names, File.cpp:line, ID or error message text"),
           "budget": dict(_I, description="Max characters of the answer (default by project size)"),
           "scope": dict(_S, description="Optional directory to focus on, e.g. Billing")}, ["query"])),
    ("mfc_refs", "Where a member variable is written (first) and read: Class::m_field or m_field.",
     _obj({"field": _S}, ["field"])),
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

INSTRUCTIONS = (
    "Offline code map of a legacy C++/MFC codebase. Call mfc_explore FIRST for any bug, question or before an "
    "edit, before opening files; one call usually answers. Treat the source it returns as already read: do not "
    "re-open or grep those lines. If you need more, call mfc_explore again with more specific names (a function "
    "from 'Not shown', Class::Method, File.cpp:a-b from an elision marker). Do not rebuild call flows by hand: "
    "name both ends and let the tool find the path. Functions flagged msg-handler, update-ui-handler or "
    "framework-entry are called by MFC (message map / virtual override), not by other code.")

DEFAULT_TOOLS = "explore"
ENV_TOOLS = "MFCGRAPH_MCP_TOOLS"


def enabled_tools(env=None):
    """Tool names exposed: env MFCGRAPH_MCP_TOOLS="explore,trace,callers" (mfc_ prefix optional; "all")."""
    env = os.environ if env is None else env
    raw = env.get(ENV_TOOLS, "") or DEFAULT_TOOLS
    names = {"mfc_" + x.strip().lower().replace("mfc_", "", 1) for x in raw.split(",") if x.strip()}
    if "mfc_all" in names:
        return [t[0] for t in TOOLS]
    return [t[0] for t in TOOLS if t[0] in names]


def tool_list(env=None):
    on = set(enabled_tools(env))
    return [{"name": n, "description": d, "inputSchema": sc} for n, d, sc in TOOLS if n in on]


def _int(a, k, d):
    v = a.get(k, d)
    try:
        return int(v)
    except (TypeError, ValueError):
        return d


def _run_tool(g, index_path, name, a, enabled=None):
    if enabled is not None and name not in enabled:
        return "tool not enabled: %s (set %s)" % (name, ENV_TOOLS), True
    if name == "mfc_explore":
        b = _int(a, "budget", 0)
        return explore(g, str(a.get("query", "")), b if b > 0 else None, str(a.get("scope", "")) or None), False
    if name == "mfc_refs":
        return q_refs(g, str(a.get("field", ""))), False
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


def run_mcp_server(index_path, stdin=None, stdout=None):
    out = stdout if stdout is not None else sys.stdout.buffer
    inp = stdin if stdin is not None else sys.stdin.buffer
    enabled = set(enabled_tools())

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

    for raw in inp:
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
            result = {"tools": tool_list()}
        elif method == "tools/call":
            name = params.get("name", "")
            args = params.get("arguments") or {}
            if g is None:
                text, is_error = "Index not available: " + err, True
            else:
                try:
                    text, is_error = _run_tool(g, index_path, name, args, enabled)
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
