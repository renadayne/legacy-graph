"""Windows resource script parser: dialogs, menus, accelerators, toolbars,
string tables. Tolerant: unknown resource types are skipped."""
from .lexer import IDENT, NUMBER, STRING, PUNCT, PP

CONTROL_KEYWORDS = frozenset("""LTEXT RTEXT CTEXT PUSHBUTTON DEFPUSHBUTTON EDITTEXT COMBOBOX LISTBOX GROUPBOX
CONTROL CHECKBOX AUTOCHECKBOX STATE3 AUTO3STATE RADIOBUTTON AUTORADIOBUTTON ICON SCROLLBAR PUSHBOX""".split())

_HEADER_WORDS = frozenset("""LANGUAGE CHARACTERISTICS VERSION FILEVERSION PRODUCTVERSION FILEFLAGSMASK FILEFLAGS
FILEOS FILETYPE FILESUBTYPE""".split())


def _is_begin(t):
    return (t[0] == IDENT and t[1] == "BEGIN") or (t[0] == PUNCT and t[1] == "{")


def _is_end(t):
    return (t[0] == IDENT and t[1] == "END") or (t[0] == PUNCT and t[1] == "}")


def strip_menu_text(s):
    tab = s.find("\\t")
    if tab >= 0:
        s = s[:tab]
    tab = s.find("\t")
    if tab >= 0:
        s = s[:tab]
    r = []
    i = 0
    while i < len(s):
        if s[i] == "&":
            if i + 1 < len(s) and s[i + 1] == "&":
                r.append("&")
                i += 1
            i += 1
            continue
        r.append(s[i])
        i += 1
    return "".join(r).strip()


class RcWalker:
    def __init__(self, toks, file_index, out):
        self.t = toks
        self.file = file_index
        self.out = out
        self.n = len(toks)

    def run(self):
        t, n = self.t, self.n
        i = 0
        while i < n:
            k = t[i]
            if k[0] == PP:
                i += 1
                continue
            if k[0] == IDENT and k[1] == "STRINGTABLE":
                i = self.parse_stringtable(i + 1)
                continue
            if k[0] in (IDENT, NUMBER) and i + 1 < n and t[i + 1][0] == IDENT:
                typ = t[i + 1][1]
                if typ in ("DIALOG", "DIALOGEX"):
                    i = self.parse_dialog(i)
                    continue
                if typ in ("MENU", "MENUEX"):
                    i = self.parse_menu(i)
                    continue
                if typ == "ACCELERATORS":
                    i = self.parse_accel(i)
                    continue
                if typ == "TOOLBAR":
                    i = self.parse_toolbar(i)
                    continue
                line = t[i][2]
                j = i + 2
                while j < n and t[j][2] == line and not _is_begin(t[j]):
                    j += 1
                while (j < n and t[j][0] == IDENT and not _is_begin(t[j]) and t[j][2] != line
                       and t[j][1] in _HEADER_WORDS):
                    l2 = t[j][2]
                    while j < n and t[j][2] == l2:
                        j += 1
                if j < n and _is_begin(t[j]):
                    j = self.skip_block(j)
                i = j
                continue
            i += 1

    def skip_block(self, j):
        t, n = self.t, self.n
        depth = 0
        while j < n:
            if _is_begin(t[j]):
                depth += 1
            elif _is_end(t[j]):
                depth -= 1
                if depth == 0:
                    return j + 1
            j += 1
        return n

    def find_begin(self, j):
        while j < self.n and not _is_begin(self.t[j]):
            j += 1
        return j

    def line_tokens(self, j):
        """Returns (indices, new_j) for one logical line inside a block."""
        t, n = self.t, self.n
        r = []
        if j >= n:
            return r, j
        line = t[j][2]
        while j < n and t[j][2] == line and not _is_begin(t[j]) and not _is_end(t[j]):
            r.append(j)
            j += 1
        while r and t[r[-1]][1] == "," and j < n and not _is_begin(t[j]) and not _is_end(t[j]):
            line = t[j][2]
            while j < n and t[j][2] == line and not _is_begin(t[j]) and not _is_end(t[j]):
                r.append(j)
                j += 1
        return r, j

    def parse_dialog(self, i):
        t, n = self.t, self.n
        d = {"file": self.file, "id": t[i][1], "caption": "", "line": t[i][2], "controls": []}
        j = i + 2
        while j < n and not _is_begin(t[j]):
            if t[j][0] == IDENT and t[j][1] == "CAPTION" and j + 1 < n and t[j + 1][0] == STRING:
                d["caption"] = t[j + 1][1]
            j += 1
        if j >= n:
            return j
        end = self.skip_block(j)
        j += 1
        while j < end - 1:
            if t[j][0] == IDENT and t[j][1] in CONTROL_KEYWORDS:
                ctype, cline = t[j][1], t[j][2]
                k = j + 1
                args = []
                while k < end - 1 and not (t[k][0] == IDENT and t[k][1] in CONTROL_KEYWORDS and t[k][2] != cline):
                    args.append(k)
                    k += 1
                parts = []
                cur = ""
                for a in args:
                    if t[a][0] == PUNCT and t[a][1] == ",":
                        parts.append(cur.strip())
                        cur = ""
                        continue
                    cur += ("" if not cur else " ") + t[a][1]
                parts.append(cur.strip())
                text_first = ctype not in ("EDITTEXT", "COMBOBOX", "LISTBOX", "SCROLLBAR")
                text, cid = "", ""
                if text_first and len(parts) >= 2:
                    text = strip_menu_text(parts[0])
                    cid = parts[1]
                elif parts:
                    cid = parts[0]
                if cid:
                    d["controls"].append((ctype, text, cid, cline))
                j = k
                continue
            j += 1
        self.out.dialogs.append(d)
        return end

    def parse_menu(self, i):
        t = self.t
        menu_id = t[i][1]
        j = self.find_begin(i + 2)
        if j >= self.n:
            return j
        end = self.skip_block(j)
        path = []
        depth_at_popup = []
        depth = 0
        pending = ""
        k = j
        while k < end:
            tok = t[k]
            if _is_begin(tok):
                depth += 1
                if pending or depth > 1:
                    path.append(pending)
                    depth_at_popup.append(depth)
                pending = ""
                k += 1
                continue
            if _is_end(tok):
                if depth_at_popup and depth_at_popup[-1] == depth:
                    depth_at_popup.pop()
                    path.pop()
                depth -= 1
                k += 1
                continue
            if tok[0] == IDENT and tok[1] == "POPUP" and k + 1 < end and t[k + 1][0] == STRING:
                pending = strip_menu_text(t[k + 1][1])
                k += 2
                continue
            if tok[0] == IDENT and tok[1] == "MENUITEM":
                if k + 1 < end and t[k + 1][0] == IDENT and t[k + 1][1] == "SEPARATOR":
                    k += 1
                    continue
                if k + 3 < end and t[k + 1][0] == STRING and t[k + 2][1] == ",":
                    p = [s for s in path if s] + [strip_menu_text(t[k + 1][1])]
                    self.out.uiitems.append({"file": self.file, "kind": "menu", "owner": menu_id,
                                             "label": " > ".join(p), "id": t[k + 3][1], "line": tok[2]})
            k += 1
        return end

    def parse_accel(self, i):
        t = self.t
        owner = t[i][1]
        j = self.find_begin(i + 2)
        if j >= self.n:
            return j
        end = self.skip_block(j)
        j += 1
        while j < end - 1:
            lt, j2 = self.line_tokens(j)
            if not lt:
                j += 1
                continue
            j = j2
            parts = []
            cur = ""
            for a in lt:
                if t[a][1] == "," and t[a][0] == PUNCT:
                    parts.append(cur.strip())
                    cur = ""
                else:
                    piece = '"' + t[a][1] + '"' if t[a][0] == STRING else t[a][1]
                    cur += ("" if not cur else " ") + piece
            parts.append(cur.strip())
            if len(parts) < 2:
                continue
            key = parts[0]
            if len(key) >= 2 and key[0] == '"':
                key = key[1:-1]
            if key.startswith("VK_"):
                key = key[3:]
            mods = ""
            for p in parts[2:]:
                if p == "CONTROL":
                    mods += "Ctrl+"
                elif p == "SHIFT":
                    mods += "Shift+"
                elif p == "ALT":
                    mods += "Alt+"
            if key and key[0] == "^" and len(key) == 2:
                mods += "Ctrl+"
                key = key[1:]
            self.out.uiitems.append({"file": self.file, "kind": "accel", "owner": owner, "label": mods + key,
                                     "id": parts[1], "line": t[lt[0]][2]})
        return end

    def parse_toolbar(self, i):
        t = self.t
        owner = t[i][1]
        j = self.find_begin(i + 2)
        if j >= self.n:
            return j
        end = self.skip_block(j)
        idx = 0
        for k in range(j, end):
            if t[k][0] == IDENT and t[k][1] == "BUTTON" and k + 1 < end:
                idx += 1
                self.out.uiitems.append({"file": self.file, "kind": "toolbar", "owner": owner,
                                         "label": "button %d" % idx, "id": t[k + 1][1], "line": t[k][2]})
        return end

    def parse_stringtable(self, j):
        t = self.t
        j = self.find_begin(j)
        if j >= self.n:
            return j
        end = self.skip_block(j)
        j += 1
        while j < end - 1:
            lt, j2 = self.line_tokens(j)
            if not lt:
                j += 1
                continue
            j = j2
            sid, text = "", ""
            for a in lt:
                if not sid and t[a][0] in (IDENT, NUMBER):
                    sid = t[a][1]
                elif t[a][0] == STRING:
                    text += t[a][1]
            if sid and text:
                self.out.strings.append((self.file, sid, text, t[lt[0]][2]))
        return end


def extract_rc(toks, file_index, out):
    RcWalker(toks, file_index, out).run()
