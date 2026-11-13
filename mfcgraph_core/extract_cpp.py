"""Heuristic, error-tolerant C++ structure extraction with MFC awareness.

Not a compiler front end: walks the token stream with a namespace/class scope
stack, recognises function definitions by the "name ( ... ) [qualifiers] {"
shape and scans bodies for calls. MFC constructs (message maps, DDX,
RUNTIME_CLASS, IDD, IMPLEMENT_*) are recognised explicitly.
"""
import re

from .lexer import IDENT, NUMBER, STRING, CHAR, PUNCT, PP
from .win32 import scan_switches, scan_wiring
from .model import RawCall, RawFunc, RawClass, RawMsgEntry, RawMsgMap

KEYWORDS = frozenset("""
if else for while do switch case default return sizeof catch try throw new delete typeid alignof alignas
decltype static_cast dynamic_cast reinterpret_cast const_cast goto break continue using typedef template
typename namespace class struct union enum public private protected virtual static const volatile inline
explicit friend operator this __declspec __try __except __finally __leave __stdcall __cdecl __fastcall
extern register auto mutable unsigned signed int char short long float double bool void wchar_t noexcept
override final nullptr true false defined static_assert afx_msg __forceinline __inline constexpr and or
not co_return co_await __super""".split())

CALL_STOP = frozenset("""
_T TEXT _TEXT ASSERT VERIFY TRACE TRACE0 TRACE1 TRACE2 TRACE3 ASSERT_VALID ASSERT_KINDOF RGB MAKELONG
MAKEWORD LOWORD HIWORD LOBYTE HIBYTE MAKEWPARAM MAKELPARAM MAKEINTRESOURCE _countof ARRAYSIZE
UNREFERENCED_PARAMETER UNUSED UNUSED_ALWAYS DEBUG_NEW ENSURE ENSURE_VALID ATLASSERT ATLTRACE SUCCEEDED
FAILED _ASSERTE _ASSERT min max __min __max STATIC_DOWNCAST DYNAMIC_DOWNCAST offsetof va_start va_end
va_arg AFX_MANAGE_STATE METHOD_PROLOGUE USES_CONVERSION""".split())

SEND_APIS = frozenset("""
SendMessage PostMessage SendMessageW SendMessageA PostMessageW PostMessageA SendNotifyMessage
PostThreadMessage SendDlgItemMessage SendMessageTimeout SendMessageToDescendants""".split())

WM_HANDLERS = {
    "CREATE": "OnCreate", "DESTROY": "OnDestroy", "PAINT": "OnPaint", "SIZE": "OnSize", "MOVE": "OnMove",
    "CLOSE": "OnClose", "TIMER": "OnTimer", "ERASEBKGND": "OnEraseBkgnd", "CTLCOLOR": "OnCtlColor",
    "CTLCOLOR_REFLECT": "CtlColor", "SYSCOMMAND": "OnSysCommand", "QUERYDRAGICON": "OnQueryDragIcon",
    "LBUTTONDOWN": "OnLButtonDown", "LBUTTONUP": "OnLButtonUp", "LBUTTONDBLCLK": "OnLButtonDblClk",
    "RBUTTONDOWN": "OnRButtonDown", "RBUTTONUP": "OnRButtonUp", "RBUTTONDBLCLK": "OnRButtonDblClk",
    "MBUTTONDOWN": "OnMButtonDown", "MBUTTONUP": "OnMButtonUp", "MOUSEMOVE": "OnMouseMove",
    "MOUSEWHEEL": "OnMouseWheel", "MOUSELEAVE": "OnMouseLeave", "KEYDOWN": "OnKeyDown", "KEYUP": "OnKeyUp",
    "CHAR": "OnChar", "SYSKEYDOWN": "OnSysKeyDown", "SETFOCUS": "OnSetFocus", "KILLFOCUS": "OnKillFocus",
    "HSCROLL": "OnHScroll", "VSCROLL": "OnVScroll", "CONTEXTMENU": "OnContextMenu", "DROPFILES": "OnDropFiles",
    "GETMINMAXINFO": "OnGetMinMaxInfo", "SETCURSOR": "OnSetCursor", "SHOWWINDOW": "OnShowWindow",
    "ACTIVATE": "OnActivate", "ACTIVATEAPP": "OnActivateApp", "NCDESTROY": "OnNcDestroy",
    "NCHITTEST": "OnNcHitTest", "NCPAINT": "OnNcPaint", "DRAWITEM": "OnDrawItem", "MEASUREITEM": "OnMeasureItem",
    "INITMENUPOPUP": "OnInitMenuPopup", "MENUSELECT": "OnMenuSelect", "COPYDATA": "OnCopyData",
    "SETTINGCHANGE": "OnSettingChange", "ENDSESSION": "OnEndSession", "QUERYENDSESSION": "OnQueryEndSession",
    "WINDOWPOSCHANGED": "OnWindowPosChanged", "WINDOWPOSCHANGING": "OnWindowPosChanging", "SIZING": "OnSizing",
    "ENABLE": "OnEnable", "MOUSEACTIVATE": "OnMouseActivate", "DEVICECHANGE": "OnDeviceChange",
    "HELPINFO": "OnHelpInfo", "NOTIFYFORMAT": "OnNotifyFormat", "GETDLGCODE": "OnGetDlgCode",
    "PARENTNOTIFY": "OnParentNotify", "CAPTURECHANGED": "OnCaptureChanged", "NCCALCSIZE": "OnNcCalcSize",
    "NCLBUTTONDOWN": "OnNcLButtonDown", "CANCELMODE": "OnCancelMode", "SYSCOLORCHANGE": "OnSysColorChange",
    "PALETTECHANGED": "OnPaletteChanged", "QUERYNEWPALETTE": "OnQueryNewPalette", "NCCREATE": "OnNcCreate",
    "CHILDACTIVATE": "OnChildActivate", "MDIACTIVATE": "OnMDIActivate", "INITMENU": "OnInitMenu",
    "ENTERIDLE": "OnEnterIdle", "COMPAREITEM": "OnCompareItem", "DELETEITEM": "OnDeleteItem",
    "CHARTOITEM": "OnCharToItem", "VKEYTOITEM": "OnVKeyToItem", "STYLECHANGED": "OnStyleChanged",
    "TCARD": "OnTCard", "DESTROYCLIPBOARD": "OnDestroyClipboard", "RENDERFORMAT": "OnRenderFormat",
    "CLIPBOARDUPDATE": "OnClipboardUpdate", "POWERBROADCAST": "OnPowerBroadcast", "DPICHANGED": "OnDpiChanged",
    "NCMOUSEMOVE": "OnNcMouseMove", "SYSCHAR": "OnSysChar", "SYSKEYUP": "OnSysKeyUp", "TIMECHANGE": "OnTimeChange",
    "FONTCHANGE": "OnFontChange", "SPOOLERSTATUS": "OnSpoolerStatus", "DEVMODECHANGE": "OnDevModeChange",
    "RASKCBFORMATNAME": "OnAskCbFormatName", "HSCROLL_REFLECT": "HScroll", "VSCROLL_REFLECT": "VScroll",
    "DRAWITEM_REFLECT": "DrawItem", "MEASUREITEM_REFLECT": "MeasureItem",
}

MESSAGE_MACROS = frozenset(["ON_MESSAGE", "ON_REGISTERED_MESSAGE", "ON_THREAD_MESSAGE",
                            "ON_REGISTERED_THREAD_MESSAGE", "ON_MESSAGE_VOID"])


def is_all_caps_ident(s):
    if len(s) < 2:
        return False
    letter = False
    for c in s:
        if "A" <= c <= "Z":
            letter = True
        elif not ("0" <= c <= "9" or c == "_"):
            return False
    return letter


def _wordch(c):
    return c.isascii() and (c.isalnum() or c == "_")


_ESCAPE = re.compile(r"\\(?:x[0-9A-Fa-f]+|[0-7]{1,3}|.)")
_FORMAT = re.compile(r"%[-+ #0]*(?:\d+|\*)?(?:\.(?:\d+|\*))?(?:hh|h|ll|l|L|z|j|t|I64|I32|I)?[A-Za-z%]")
STRING_MAX = 200
_RE_RESOURCE_ID = re.compile(r"^(?:ID|IDD|IDC|IDS|IDR|IDM|IDP|WM|UWM)_[A-Z0-9_]+$")
WRITE_OPS = frozenset(["=", "+=", "-=", "*=", "/=", "%=", "|=", "&=", "^=", "<<=", ">>=", "++", "--"])


def clean_literal(text):
    """Return the literal text to index, or "" if it has < 3 letters once escapes/format specs are removed."""
    rest = _FORMAT.sub("", _ESCAPE.sub("", text))
    if sum(1 for c in rest if c.isalpha()) < 3:
        return ""
    text = " ".join(text.split())  # tabs/newlines (raw strings) -> single spaces
    return text[:STRING_MAX]


def join_tokens(t, b, e):
    parts = []
    last = ""
    for i in range(b, e):
        k, s, _ = t[i]
        if k == STRING:
            s = '"' + s + '"'
        elif k == CHAR:
            s = "'" + s + "'"
        if parts:
            wl = _wordch(last) or last == '"'
            wr = bool(s) and (_wordch(s[0]) or s[0] == '"')
            if (wl and wr) or s == "*" or s == "&" or last == ",":
                parts.append(" ")
        parts.append(s)
        if s:
            last = s[-1]
    return "".join(parts)


class _Scope:
    __slots__ = ("kind", "name", "cls", "close")

    def __init__(self, kind, name, cls, close):
        self.kind, self.name, self.cls, self.close = kind, name, cls, close


NS, CLS = 0, 1


class CppWalker:
    def __init__(self, toks, file_index, out):
        self.t = toks
        self.file = file_index
        self.out = out
        self.n = len(toks)
        self.scopes = []

    # ---- helpers ----
    def is_p(self, i, s):
        return 0 <= i < self.n and self.t[i][0] == PUNCT and self.t[i][1] == s

    def is_id(self, i):
        return 0 <= i < self.n and self.t[i][0] == IDENT

    def in_class(self):
        return bool(self.scopes) and self.scopes[-1].kind == CLS

    def compute_matches(self):
        n, t = self.n, self.t
        bm = [-1] * n
        pm = [-1] * n
        bs, ps = [], []
        err = False
        for i in range(n):
            k, s, _ = t[i]
            if k != PUNCT:
                continue
            if s == "{":
                bs.append(i)
            elif s == "}":
                if bs:
                    j = bs.pop()
                    bm[j] = i
                    bm[i] = j
                else:
                    err = True
            elif s == "(":
                ps.append(i)
            elif s == ")":
                if ps:
                    j = ps.pop()
                    pm[j] = i
                    pm[i] = j
        if bs or err:
            self.out.files[self.file].brace_error = True
        self.bm, self.pm = bm, pm

    def skip_to_semicolon(self, i):
        t, n = self.t, self.n
        while i < n and not (t[i][0] == PUNCT and t[i][1] == ";"):
            i += 1
        return i + 1

    def skip_angles(self, i):
        t, n = self.t, self.n
        depth = 0
        while i < n:
            k, s, _ = t[i]
            if k == PUNCT:
                if s == "<":
                    depth += 1
                elif s == ">":
                    depth -= 1
                    if depth <= 0:
                        return i + 1
                elif s == ">>":
                    depth -= 2
                    if depth <= 0:
                        return i + 1
                elif s == "{" or s == ";":
                    return i
            i += 1
        return i

    def ns_path(self):
        return "::".join(s.name for s in self.scopes if s.kind == NS and s.name)

    def class_path(self):
        return "::".join(s.name for s in self.scopes if s.kind == CLS)

    def current_class(self):
        for s in reversed(self.scopes):
            if s.kind == CLS:
                return s.cls
        return -1

    # ---- main walk ----
    def run(self):
        self.compute_matches()
        t, n, bm = self.t, self.n, self.bm
        i = 0
        stmt = 0
        while i < n:
            if self.scopes and i == self.scopes[-1].close:
                sc = self.scopes[-1]
                if sc.kind == CLS and sc.cls >= 0:
                    self.out.classes[sc.cls].end = t[i][2]
                self.scopes.pop()
                i += 1
                stmt = i
                continue
            k, s, line = t[i]
            if k == PP:
                self.handle_pp(t[i])
                i += 1
                stmt = i
                continue
            if k == PUNCT and s == ";":
                if self.in_class() and i > stmt:
                    self.analyze_field(stmt, i)
                i += 1
                stmt = i
                continue
            if k == PUNCT and s == "}":
                i += 1
                stmt = i
                continue
            if k == IDENT:
                if s == "template" and self.is_p(i + 1, "<"):
                    i = self.skip_angles(i + 1)
                    continue
                if s == "namespace":
                    if i > 0 and t[i - 1][1] == "using":
                        i = self.skip_to_semicolon(i)
                        continue
                    j = i + 1
                    name = ""
                    while j < n and (t[j][0] == IDENT or t[j][1] == "::"):
                        name += t[j][1]
                        j += 1
                    if j < n and t[j][1] == "{" and bm[j] > 0:
                        self.scopes.append(_Scope(NS, name, -1, bm[j]))
                        i = j + 1
                        stmt = i
                        continue
                    i = self.skip_to_semicolon(i)
                    continue
                if (s == "extern" and i + 2 < n and t[i + 1][0] == STRING and t[i + 2][1] == "{"
                        and bm[i + 2] > 0):
                    self.scopes.append(_Scope(NS, "", -1, bm[i + 2]))
                    i += 3
                    stmt = i
                    continue
                if (s in ("class", "struct", "union") and not (i > 0 and t[i - 1][1] == "enum")
                        and not (i > 0 and t[i - 1][1] in ("friend", "<", ","))):
                    ni = self.try_class(i)
                    if ni > i:
                        i = ni
                        stmt = i
                        continue
                if s == "enum":
                    j = i + 1
                    while j < n and t[j][1] != "{" and t[j][1] != ";":
                        j += 1
                    if j < n and t[j][1] == "{" and bm[j] > 0:
                        if self.in_class():
                            self.scan_idd(j, bm[j])
                        i = bm[j] + 1
                        continue
                    i = j + 1
                    stmt = i
                    continue
                if self.in_class() and s in ("public", "private", "protected") and self.is_p(i + 1, ":"):
                    i += 2
                    stmt = i
                    continue
            if k == PUNCT and s == "(" and i > 0:
                ni = self.handle_paren(i, stmt)
                if ni > i:
                    i = ni
                    stmt = i
                    continue
            if k == PUNCT and s == "{":
                if bm[i] > 0:
                    i = bm[i] + 1
                    continue
                i += 1
                continue
            i += 1

    def handle_pp(self, tok):
        d = tok[1]
        if d.startswith("include"):
            a = -1
            for idx, ch in enumerate(d):
                if ch in "\"<":
                    a = idx
                    break
            if a < 0:
                return
            close = '"' if d[a] == '"' else ">"
            b = d.find(close, a + 1)
            if b < 0:
                return
            self.out.includes.append((self.file, d[a + 1:b], tok[2]))
        elif d.startswith("define"):
            rest = d[6:].strip()
            e = 0
            while e < len(rest) and (rest[e].isascii() and (rest[e].isalnum() or rest[e] == "_")):
                e += 1
            if e == 0:
                return
            name = rest[:e]
            if e < len(rest) and rest[e] == "(":
                return
            self.out.defines.append((self.file, name, rest[e:].strip(), tok[2]))

    def scan_idd(self, b, e):
        cls = self.current_class()
        if cls < 0:
            return
        t = self.t
        for j in range(b, e - 2):
            if self.is_id(j) and t[j][1] == "IDD" and self.is_p(j + 1, "=") and t[j + 2][0] != PUNCT:
                self.out.classes[cls].idd = t[j + 2][1]

    def try_class(self, i):
        t, n, pm, bm = self.t, self.n, self.pm, self.bm
        j = i + 1
        name = ""
        while j < n:
            if self.is_id(j) and t[j][1] == "__declspec" and self.is_p(j + 1, "(") and pm[j + 1] > 0:
                j = pm[j + 1] + 1
                continue
            if self.is_id(j):
                if t[j][1] not in ("final", "sealed"):
                    name = t[j][1]
                j += 1
                continue
            if self.is_p(j, "::"):
                j += 1
                continue
            if self.is_p(j, "<"):
                j = self.skip_angles(j)
                continue
            break
        if j >= n:
            return i
        bases = []
        if self.is_p(j, ":"):
            cur = ""
            depth = 0
            j += 1
            while j < n:
                k, s, _ = t[j]
                if k == PUNCT and s == "{" and depth == 0:
                    break
                if k == PUNCT and s == ";":
                    return i
                if k == PUNCT and s == "<":
                    depth += 1
                    j += 1
                    continue
                if k == PUNCT and s in (">", ">>"):
                    depth -= 2 if s == ">>" else 1
                    j += 1
                    continue
                if depth > 0:
                    j += 1
                    continue
                if k == PUNCT and s == ",":
                    if cur:
                        bases.append(cur)
                    cur = ""
                    j += 1
                    continue
                if k == IDENT:
                    if s not in ("public", "private", "protected", "virtual"):
                        cur += s
                elif s == "::":
                    cur += "::"
                j += 1
            if cur:
                bases.append(cur)
        if not self.is_p(j, "{") or bm[j] < 0:
            return i
        if not name:
            return bm[j] + 1
        c = RawClass()
        c.file = self.file
        outer = self.class_path()
        c.name = name if not outer else outer + "::" + name
        c.ns = self.ns_path()
        c.bases = bases
        c.line = t[i][2]
        self.out.classes.append(c)
        self.scopes.append(_Scope(CLS, name, len(self.out.classes) - 1, bm[j]))
        return j + 1

    def analyze_field(self, b, e):
        cls = self.current_class()
        if cls < 0:
            return
        t = self.t
        for j in range(b, e):
            k, s, _ = t[j]
            if k == PUNCT and s in ("(", "{"):
                return
            if k == IDENT and s in ("typedef", "using", "friend", "enum"):
                return
        typ = ""
        seg_b = b
        depth = 0
        skip_types = ("static", "const", "mutable", "volatile", "unsigned", "signed", "struct", "class",
                      "typename", "constexpr")
        for j in range(b, e + 1):
            end = j == e
            if not end and t[j][0] == PUNCT:
                s = t[j][1]
                if s == "<":
                    depth += 1
                elif s == ">":
                    depth -= 1
                elif s == ">>":
                    depth -= 2
            if end or (depth == 0 and self.is_p(j, ",")):
                name = ""
                for q in range(seg_b, j):
                    k, s, _ = t[q]
                    if k == PUNCT and s in ("=", "[", ":"):
                        break
                    if k == IDENT:
                        if not typ and s not in skip_types:
                            typ = s
                        name = s
                if name and typ and name != typ:
                    self.out.classes[cls].fields[name] = typ
                seg_b = j + 1

    def split_args(self, p):
        t, pm = self.t, self.pm
        close = pm[p]
        args = []
        if close < 0:
            return args
        cur = []
        depth = 0
        for j in range(p + 1, close):
            k, s, _ = t[j]
            if k == PUNCT:
                if s in ("(", "{", "["):
                    depth += 1
                elif s in (")", "}", "]"):
                    depth -= 1
                elif s == "," and depth == 0:
                    args.append(cur)
                    cur = []
                    continue
            cur.append(j)
        if cur or args:
            args.append(cur)
        return args

    def arg_text(self, a):
        if not a:
            return ""
        return join_tokens(self.t, a[0], a[-1] + 1)

    @staticmethod
    def clean_handler(h):
        return h.replace("&", "").replace(" ", "").strip()

    def handle_paren(self, p, stmt):
        t, n, pm, bm = self.t, self.n, self.pm, self.bm
        close = pm[p]
        if close < 0:
            return p
        j = p - 1
        if self.is_id(j):
            name = t[j][1]
            if self.is_p(j - 1, "~"):
                name = "~" + name
                j -= 1
            elif j - 1 >= 0 and t[j - 1][1] == "operator":
                name = "operator " + name
                j -= 1
        elif t[j][0] == PUNCT and j - 1 >= 0 and t[j - 1][1] == "operator":
            name = "operator" + t[j][1]
            j -= 1
        else:
            return p
        if name in KEYWORDS:
            return p
        qual = ""
        q = j
        while q - 2 >= 0 and self.is_p(q - 1, "::") and self.is_id(q - 2):
            qual = t[q - 2][1] + ("" if not qual else "::" + qual)
            q -= 2
        if q - 1 >= 0 and t[q - 1][0] == PUNCT and t[q - 1][1] in (".", "->", "=", "(", ","):
            return p

        if not qual and is_all_caps_ident(name):
            after = close + 1
            if not self.is_p(after, "{"):
                self.handle_scope_macro(name, p)
                if name in ("BEGIN_MESSAGE_MAP", "BEGIN_TEMPLATE_MESSAGE_MAP"):
                    return self.parse_msgmap(p)
                return after + 1 if self.is_p(after, ";") else after

        a = close + 1
        while a < n:
            k, s, _ = t[a]
            if k == IDENT and s in ("const", "volatile", "override", "final", "PURE", "noexcept", "throw", "sealed"):
                if s in ("throw", "noexcept") and self.is_p(a + 1, "(") and pm[a + 1] > 0:
                    a = pm[a + 1] + 1
                else:
                    a += 1
                continue
            if k == PUNCT and s in ("&", "&&"):
                a += 1
                continue
            if k == PUNCT and s == "->":
                while a < n and not self.is_p(a, "{") and not self.is_p(a, ";"):
                    a += 1
                continue
            break
        if a >= n:
            return p

        in_cls = self.in_class()
        body = -1
        decl = False
        if self.is_p(a, "{"):
            body = a
        elif self.is_p(a, ":"):
            b = a + 1
            while b < n:
                while b < n and (self.is_id(b) or self.is_p(b, "::")):
                    b += 1
                if self.is_p(b, "<"):
                    b = self.skip_angles(b)
                if self.is_p(b, "(") and pm[b] > 0:
                    b = pm[b] + 1
                elif self.is_p(b, "{") and bm[b] > 0:
                    b = bm[b] + 1
                else:
                    break
                if self.is_p(b, ","):
                    b += 1
                    continue
                break
            if self.is_p(b, "{"):
                body = b
            else:
                return p
        elif self.is_p(a, ";") or self.is_p(a, "="):
            decl = True
        elif self.is_id(a) and t[a][1] == "try" and self.is_p(a + 1, "{"):
            body = a + 1
        else:
            return p

        is_virtual = any(self.is_id(s_) and t[s_][1] == "virtual" for s_ in range(stmt, q))

        if decl:
            end = a if self.is_p(a, ";") else self.skip_to_semicolon(a) - 1
            if in_cls and not qual:
                f = RawFunc()
                f.file = self.file
                f.cls = self.class_path()
                f.ns = self.ns_path()
                f.name = name
                f.line = t[j][2]
                f.end = f.line
                f.sig = join_tokens(t, stmt, close + 1)
                if len(f.sig) > 240:
                    f.sig = f.sig[:240] + "..."
                f.is_def = False
                f.is_virtual = is_virtual
                self.out.funcs.append(f)
            return end + 1

        e = bm[body]
        if e < 0:
            e = n - 1
        f = RawFunc()
        f.file = self.file
        if qual:
            outer = self.class_path()
            f.cls = qual if not outer else outer + "::" + qual
        elif in_cls:
            f.cls = self.class_path()
        f.ns = self.ns_path()
        f.name = name
        f.line = t[j][2]
        f.end = t[e][2]
        f.sig = join_tokens(t, stmt, close + 1)
        if len(f.sig) > 240:
            f.sig = f.sig[:240] + "..."
        f.is_def = True
        f.is_virtual = is_virtual
        self.scan_locals(f, p + 1, close)
        self.scan_body(f, body + 1, e)
        self.out.funcs.append(f)
        return e + 1

    def handle_scope_macro(self, name, p):
        if name in ("IMPLEMENT_DYNCREATE", "IMPLEMENT_DYNAMIC", "IMPLEMENT_SERIAL"):
            args = self.split_args(p)
            if len(args) >= 2:
                self.out.dynamics.append((self.file, name, self.arg_text(args[0]), self.arg_text(args[1]),
                                          self.t[p][2]))

    def parse_msgmap(self, p):
        t, n, pm = self.t, self.n, self.pm
        args = self.split_args(p)
        mm = RawMsgMap(self.file, t[p][2])
        if args:
            mm.cls = self.arg_text(args[0])
        if len(args) >= 2:
            mm.base = self.arg_text(args[-1])
        a = pm[p] + 1
        while a < n:
            if self.is_id(a) and t[a][1] == "END_MESSAGE_MAP":
                a = pm[a + 1] + 1 if (self.is_p(a + 1, "(") and pm[a + 1] > 0) else a + 1
                break
            if t[a][0] == PP:
                self.handle_pp(t[a])
                a += 1
                continue
            if self.is_p(a, "{") or self.is_p(a, "}"):
                break
            if self.is_id(a) and self.is_p(a + 1, "(") and pm[a + 1] > 0:
                self.add_msg_entry(mm, t[a][1], a + 1)
                a = pm[a + 1] + 1
                continue
            a += 1
        self.out.msgmaps.append(mm)
        return a

    def _unknown(self, macro):
        self.out.unknown_macros[macro] = self.out.unknown_macros.get(macro, 0) + 1

    def add_msg_entry(self, mm, macro, p):
        a = [self.arg_text(r) for r in self.split_args(p)]
        e = RawMsgEntry(macro, self.t[p][2])
        if macro.startswith("ON_WM_") and not a:
            e.kind = "message"
            base = macro[6:]
            if base.endswith("_REFLECT"):
                base = base[:-8]
            e.id = "WM_" + base
            e.handler = WM_HANDLERS.get(macro[6:], "")
            if not e.handler:
                self._unknown(macro)
                return
            mm.entries.append(e)
            return
        if not macro.startswith("ON_") or not a:
            if macro.startswith("ON_"):
                self._unknown(macro)
            return
        e.handler = self.clean_handler(a[-1])
        reflect = macro.endswith("_REFLECT") or macro.endswith("_REFLECT_EX")
        if macro in MESSAGE_MACROS:
            e.kind = "message"
            e.id = a[0]
        elif macro.startswith("ON_UPDATE_COMMAND_UI"):
            e.kind = "update_ui"
            e.id = a[0]
            if len(a) >= 3:
                e.id2 = a[1]
        elif macro.startswith("ON_NOTIFY") or macro.startswith("ON_CONTROL"):
            e.kind = "notify" if macro.startswith("ON_NOTIFY") else "command"
            if reflect:
                e.id = a[0]
            elif len(a) >= 4:
                e.id, e.id2 = a[1], a[2]
            elif len(a) >= 3:
                e.id = a[1]
            else:
                e.id = a[0]
        else:
            e.kind = "command"
            if len(a) < 2:
                self._unknown(macro)
                return
            e.id = a[0]
            if len(a) >= 3:
                e.id2 = a[1]
        mm.entries.append(e)

    def scan_locals(self, f, b, e):
        t, n = self.t, self.n
        loc = f.locals
        for x in range(b, min(e - 1, n - 1)):
            k, s, _ = t[x]
            if k != IDENT or s in KEYWORDS:
                continue
            k1, s1, _ = t[x + 1]
            if k1 == IDENT and s1 not in KEYWORDS and x + 2 < n and t[x + 2][0] == PUNCT:
                if t[x + 2][1] in (";", "=", ",", ")", "["):
                    loc[s1] = s
            if (x + 3 < n and k1 == PUNCT and s1 in ("*", "&") and t[x + 2][0] == IDENT
                    and t[x + 2][1] not in KEYWORDS and t[x + 3][0] == PUNCT
                    and t[x + 3][1] in (";", "=", ",", ")", "[")):
                loc[t[x + 2][1]] = s

    def scan_strings(self, f, b, e):
        """Collect string literals as (line, text); adjacent literals are joined."""
        t = self.t
        x = b
        while x < e:
            if t[x][0] != STRING:
                x += 1
                continue
            line = t[x][2]
            parts = []
            while x < e and t[x][0] == STRING:
                parts.append(t[x][1])
                x += 1
            text = clean_literal("".join(parts))
            if text:
                f.strings.append((line, text))

    def _ref_mode(self, x, b, e):
        t = self.t
        if x - 1 >= b and t[x - 1][0] == PUNCT and t[x - 1][1] in ("++", "--"):
            return "w"
        nx = x + 1
        while nx < e and self.is_p(nx, "["):  # m_arr[i] = v: skip subscripts
            depth = 0
            while nx < e:
                if self.is_p(nx, "["):
                    depth += 1
                elif self.is_p(nx, "]"):
                    depth -= 1
                    if depth == 0:
                        break
                nx += 1
            nx += 1
        if nx < e and t[nx][0] == PUNCT and t[nx][1] in WRITE_OPS:
            return "w"
        return "r"

    def scan_refs(self, f, b, e):
        """Record (name, recv, line, mode) for x.name / p->name, for m_/g_/s_ identifiers not called, and for
        resource/message ids (IDS_x, IDC_x, WM_APP_x ...) used in the body (resolved only if the id is known)."""
        t, is_p = self.t, self.is_p
        for x in range(b, e):
            k, name, line = t[x]
            if k != IDENT or name in KEYWORDS or is_p(x + 1, "(") or is_p(x + 1, "::"):
                continue
            recv = ""
            after_member = x - 1 >= b and t[x - 1][0] == PUNCT and t[x - 1][1] in (".", "->")
            if after_member:
                if x - 2 >= b and t[x - 2][0] == IDENT:
                    recv = t[x - 2][1]
                else:
                    recv = "?"
            elif not name.startswith(("m_", "g_", "s_")) and not _RE_RESOURCE_ID.match(name):
                continue
            f.refs.append((name, recv, line, self._ref_mode(x, b, e)))

    def scan_body(self, f, b, e):
        self.scan_locals(f, b, e)
        self.scan_strings(f, b, e)
        self.scan_refs(f, b, e)
        scan_switches(self, f, b, e)
        scan_wiring(self, f, b, e)
        t, pm = self.t, self.pm
        is_p, is_id = self.is_p, self.is_id
        for x in range(b, e):
            k, name, line = t[x]
            if k != IDENT or not is_p(x + 1, "("):
                continue
            if name in KEYWORDS:
                continue
            if name == "RUNTIME_CLASS":
                if is_id(x + 2):
                    f.runtime.append((t[x + 2][1], line))
                continue
            if name.startswith("DDX_"):
                args = self.split_args(x + 1)
                if len(args) >= 3:
                    f.ddx.append((name, self.arg_text(args[1]), self.arg_text(args[2]), line))
                continue
            if name.startswith("DDV_") or name in CALL_STOP:
                continue
            prev = x - 1
            if prev >= b and is_id(prev) and t[prev][1] not in KEYWORDS:
                f.locals[name] = t[prev][1]  # CRect rc(...)
                continue
            if prev >= b and is_id(prev) and t[prev][1] == "new":
                continue
            c = RawCall(name, line)
            if prev >= b and t[prev][0] == PUNCT and t[prev][1] in (".", "->"):
                c.member = True
                if prev - 1 >= b and is_id(prev - 1):
                    c.recv = t[prev - 1][1]
                elif prev - 1 >= b and is_p(prev - 1, ")") and pm[prev - 1] >= b:
                    m = pm[prev - 1]
                    if (is_p(m + 1, "(") and is_id(m + 2) and (is_p(m + 3, "*") or is_p(m + 3, "&"))
                            and is_p(m + 4, ")")):
                        c.recv_type = t[m + 2][1]
                    elif m - 1 >= b and is_id(m - 1) and t[m - 1][1] not in KEYWORDS:
                        c.recv_call = t[m - 1][1]
            elif prev >= b and is_p(prev, "::"):
                q = prev
                qual = ""
                while q - 1 >= b and is_id(q - 1):
                    qual = t[q - 1][1] + ("" if not qual else "::" + qual)
                    if q - 2 >= b and is_p(q - 2, "::"):
                        q -= 2
                    else:
                        break
                c.qual = qual if qual else "::"
            if name in SEND_APIS:
                close = pm[x + 1]
                caps = []
                if close > 0:
                    for kk in range(x + 2, close):
                        if is_id(kk) and is_all_caps_ident(t[kk][1]):
                            caps.append(t[kk][1])
                if caps:
                    f.sends.append((name, caps, line))
            f.calls.append(c)


def extract_cpp(toks, file_index, out):
    CppWalker(toks, file_index, out).run()
