"""Map parsed explore terms (explore_query.Term) to seed nodes of the graph.

Interface:
    seed(graph, terms, scope_dirs=(), query_text="") -> SeedResult
    SeedResult fields:
      seeds        {node_id: (weight, reason)}   weights summed over terms; reason = "; "-joined short reasons
      exact        set(node_id)                  named exactly (anchor / qualified): always shown in full first
      pinned_files set(file_index)               files named in the query (path / anchor)
      scope_dirs   list[str]                     directories ("Billing", "Report/Common") the query limits itself to
      focus        {node_id: set(line)}          lines worth showing inside a function (anchor, literal, ref, id use)
      file_focus   {file_index: [(a, b)]}        anchor ranges that fall outside every function
      unmatched    list[Term]                    non-word terms that matched nothing
      suggestions  {term_value: [names]}         "did you mean" for unmatched ident / qualified terms
      texts        [(func, line, text)]          literals matched by quoted terms (for the Flow section)

Weights (tuned in S9; every number is a general principle, not a fit to one sample):
    anchor 10 (exact) · qualified 8 (exact) · ident 6 (<= 5 definitions; more -> 30 split evenly)
    id 5 (handlers via handled_by, senders, functions using the id) · quoted 5 (literal or UI caption)
    word 1 per match (name segment / caption / literal), at most WORD_CAP per node.
A word equal to a directory name of the tree (e.g. "billing") adds that directory to scope_dirs:
developers name the module they suspect.
Captions (menu items, dialog captions, button texts, string table) that appear verbatim inside the query text
count like a quoted term, so `bấm Tính lại thì ...` finds the "Tính lại" button without quotes.
"""
import difflib
import re
import unicodedata
from collections import namedtuple

SeedResult = namedtuple("SeedResult", "seeds exact pinned_files scope_dirs focus file_focus unmatched suggestions texts")

W_ANCHOR = 10.0
W_QUALIFIED = 8.0
W_IDENT = 6.0
W_IDENT_MAX_DEFS = 5
W_ID = 5.0
W_QUOTED = 5.0
W_WORD = 1.0
WORD_CAP = 3.0
W_REF_WRITE = 5.0     # function writing a named field
W_REF_READ = 2.0      # function reading a named field
MIN_CAPTION = 4       # shortest caption matched inside free query text

_SEG = re.compile(r"[A-Z]+(?=[A-Z][a-z])|[A-Z]?[a-z]+|[A-Z]+|\d+")


def norm(s):
    return unicodedata.normalize("NFC", s).casefold()


def clean_caption(s):
    s = s.split("\t")[0].replace("&", "")
    return s.strip().rstrip(".").strip()


def segments(name):
    """CamelCase / snake_case segments, lower-case: 'OnBnClickedRecalc' -> ['on','bn','clicked','recalc']."""
    out = []
    for part in re.split(r"[_:~]+", name):
        out.extend(m.group(0).lower() for m in _SEG.finditer(part))
    return out


def _word_hits_segment(word, segs):
    for s in segs:
        if s == word:
            return True
        if len(s) >= 4 and len(word) >= 4 and (s.startswith(word) or word.startswith(s)):
            return True
    return False


class _Seeder:
    def __init__(self, g, scope_dirs, query_text):
        self.g = g
        self.seeds = {}
        self.exact = set()
        self.pinned = set()
        self.scope = list(scope_dirs)
        self.focus = {}
        self.file_focus = {}
        self.unmatched = []
        self.suggestions = {}
        self.texts = []
        self.word_score = {}
        self.qtext = norm(query_text or "")
        self._index()

    # ---- lookup tables ----
    def _index(self):
        g = self.g
        self.funcs_by_name, self.funcs_by_qname, self.classes_by_name = {}, {}, {}
        for n in g.nodes:
            if n.kind == "function":
                self.funcs_by_name.setdefault(n.name, []).append(n.id)
                self.funcs_by_qname.setdefault(n.qname, []).append(n.id)
            elif n.kind == "class":
                self.classes_by_name.setdefault(n.name, []).append(n.id)
        self.ref_targets = {}
        for (fn, line, target, mode) in g.refs:
            self.ref_targets.setdefault(target, []).append((fn, line, mode))
        self.ids = {n.name: n.id for n in g.nodes if n.kind == "id"}
        self.dirs = {}
        for i, f in enumerate(g.files):
            parts = f.path.split("/")[:-1]
            for k in range(1, len(parts) + 1):
                self.dirs.setdefault(norm(parts[k - 1]), set()).add("/".join(parts[:k]))

    def defs(self, ids):
        """Prefer definitions over declarations."""
        d = [x for x in ids if "decl" not in self.g.nodes[x].flags.split(",")]
        return d or list(ids)

    # ---- accumulation ----
    def add(self, node, w, reason, line=None):
        old = self.seeds.get(node)
        if old is None:
            self.seeds[node] = (w, reason)
        else:
            rs = old[1] if reason in old[1].split("; ") else old[1] + "; " + reason
            self.seeds[node] = (old[0] + w, rs)
        if line:
            self.focus.setdefault(node, set()).add(line)

    def add_word(self, node, reason, line=None):
        got = self.word_score.get(node, 0.0)
        if got >= WORD_CAP:
            return
        self.word_score[node] = got + W_WORD
        self.add(node, W_WORD, reason, line)

    # ---- files ----
    def files_matching(self, path):
        p = norm(path.strip("/"))
        out = []
        for i, f in enumerate(self.g.files):
            fp = norm(f.path)
            if fp == p or fp.endswith("/" + p):
                out.append(i)
        return out

    def dir_matches(self, path):
        p = norm(path.strip("/"))
        found = set()
        for i, f in enumerate(self.g.files):
            fp = norm(f.path)
            if fp.startswith(p + "/"):
                found.add(f.path[:len(p)])
            else:
                k = fp.find("/" + p + "/")
                if k >= 0:
                    found.add(f.path[:k + 1 + len(p)])
        return sorted(found)

    def funcs_in_file(self, fi):
        return [n.id for n in self.g.nodes if n.kind == "function" and n.file == fi and n.end >= n.line
                and "decl" not in n.flags.split(",")]

    # ---- term handlers ----
    def t_anchor(self, t):
        files = self.files_matching(t.value)
        if not files:
            return False
        a, b = t.extra
        for fi in files:
            self.pinned.add(fi)
            hit = False
            for fn in self.funcs_in_file(fi):
                n = self.g.nodes[fn]
                if n.line <= b and n.end >= a:
                    hit = True
                    self.add(fn, W_ANCHOR, "anchor %s:%d" % (self.g.files[fi].path, a))
                    self.exact.add(fn)
                    lines = range(max(a, n.line), min(b, n.end) + 1)
                    for ln in (lines if len(lines) <= 20 else (lines[0], lines[-1])):
                        self.focus.setdefault(fn, set()).add(ln)
            if not hit:
                self.file_focus.setdefault(fi, []).append((a, b))
        return True

    def t_path(self, t):
        if t.extra == "file":
            files = self.files_matching(t.value)
            self.pinned.update(files)
            return bool(files)
        dirs = self.dir_matches(t.value)
        for d in dirs:
            if d not in self.scope:
                self.scope.append(d)
        return bool(dirs)

    def seed_field(self, target, w_scale, reason):
        for (fn, line, mode) in self.ref_targets.get(target, ()):
            self.add(fn, (W_REF_WRITE if mode == "w" else W_REF_READ) * w_scale,
                     "%s %s" % ("writes" if mode == "w" else "reads", reason), line)

    def t_qualified(self, t):
        v = t.value
        hits = self.funcs_by_qname.get(v) or [x for q, lst in self.funcs_by_qname.items()
                                               if q.endswith("::" + v) for x in lst]
        hits = self.defs(hits)
        cls = [n.id for n in self.g.nodes if n.kind == "class" and (n.qname == v or n.qname.endswith("::" + v))]
        fields = [x for x in self.ref_targets if x == v or x.endswith("::" + v)]
        for x in hits + cls:
            self.add(x, W_QUALIFIED, "named " + v)
            self.exact.add(x)
        for f in fields:
            self.seed_field(f, 1.0, f)
        return bool(hits or cls or fields)

    def t_ident(self, t):
        v = t.value
        found = self.defs(self.funcs_by_name.get(v, [])) + self.classes_by_name.get(v, [])
        fields = [x for x in self.ref_targets if x == v or x.endswith("::" + v)]
        if not found and not fields:
            vl = v.lower()
            found = self.defs([x for name, lst in self.funcs_by_name.items() if name.lower() == vl for x in lst])
            found += [x for name, lst in self.classes_by_name.items() if name.lower() == vl for x in lst]
        if not found and not fields:
            if v in self.ids:
                return self.t_id(t)
            return False
        if len(found) > 1 and self.pinned:
            found = [x for x in found if self.g.nodes[x].file in self.pinned] or found
        if len(found) > 1 and self.scope:
            found = [x for x in found if self.in_scope(x)] or found
        n = len(found) + len(fields)
        w = W_IDENT if n <= W_IDENT_MAX_DEFS else W_IDENT * W_IDENT_MAX_DEFS / n
        for x in found:
            self.add(x, w, "named " + v)
        for f in fields:
            self.seed_field(f, w / W_IDENT, f)
        return True

    def handlers_of_id(self, idn):
        g = self.g
        out = []
        for ei in g.out[idn]:
            e = g.edges[ei]
            if e.kind == "handled_by" and g.nodes[e.dst].kind == "function":
                out.append(e.dst)
        return out

    def seed_id(self, idn, w, reason):
        g = self.g
        name = g.nodes[idn].name
        any_hit = False
        for fn in self.handlers_of_id(idn):
            self.add(fn, w, "handles " + reason)
            any_hit = True
        for ei in g.inn[idn]:
            e = g.edges[ei]
            src = g.nodes[e.src]
            if e.kind == "sends" and src.kind == "function":
                self.add(e.src, w, "sends " + reason, e.line)
                any_hit = True
            elif e.kind == "uses_dialog":
                self.add(e.src, w, "dialog class of " + reason)
                any_hit = True
        for (fn, line, mode) in self.ref_targets.get(name, ()):
            self.add(fn, w * 0.8, "uses " + reason, line)
            any_hit = True
        return any_hit

    def t_id(self, t):
        idn = self.ids.get(t.value)
        if idn is None:
            return False
        self.seed_id(idn, W_ID, t.value)
        dn = [n.id for n in self.g.nodes if n.kind == "dialog" and n.name == t.value]
        for d in dn:
            self.seed_id(d, W_ID, t.value)
        return True

    def caption_targets(self):
        """[(caption_norm, display, node_to_seed_from, kind)] for menus, dialogs, controls, string table."""
        cached = getattr(self, "_captions", None)
        if cached is not None:
            return cached
        g = self.g
        out = []
        for n in g.nodes:
            if n.kind == "ui" and n.extra == "menu":
                label = n.name.split(": ", 1)[-1]
                leaf = clean_caption(label.split(" > ")[-1])
                for ei in g.out[n.id]:
                    out.append((norm(leaf), label, g.edges[ei].dst, "menu"))
            elif n.kind == "dialog" and n.extra.startswith('caption="'):
                out.append((norm(clean_caption(n.extra[9:-1])), n.extra, n.id, "dialog"))
            elif n.kind == "id" and 'text="' in n.extra:
                txt = n.extra[n.extra.index('text="') + 6:].rstrip('"')
                for piece in txt.split("\\n"):
                    if piece.strip():
                        out.append((norm(clean_caption(piece)), piece, n.id, "string"))
        for e in g.edges:
            if e.kind == "contains" and '"' in e.extra:
                txt = e.extra[e.extra.index('"') + 1:].rstrip('"')
                out.append((norm(clean_caption(txt)), txt, e.dst, "control"))
        self._captions = [c for c in out if c[0]]
        return self._captions

    def seed_caption(self, cap, w, why):
        _, display, node, kind = cap
        return self.seed_id(node, w, '%s "%s"' % (why, clean_caption(display)))

    def t_quoted(self, t):
        q = norm(t.value)
        hit = False
        for (fn, line, text) in self.g.texts:
            if q in norm(text):
                self.add(fn, W_QUOTED, 'contains "%s"' % text[:40], line)
                self.texts.append((fn, line, text))
                hit = True
        for cap in self.caption_targets():
            if q == cap[0] or (len(q) >= MIN_CAPTION and q in cap[0]):
                hit = self.seed_caption(cap, W_QUOTED, "caption") or hit
        return hit

    def captions_in_text(self):
        if not self.qtext:
            return
        done = set()
        for cap in self.caption_targets():
            c = cap[0]
            if len(c) < MIN_CAPTION or (c, cap[2]) in done:
                continue
            if re.search(r"(?<!\w)" + re.escape(c) + r"(?!\w)", self.qtext):
                done.add((c, cap[2]))
                self.seed_caption(cap, W_QUOTED, "caption")

    def t_word(self, t):
        w = t.value
        hit = False
        if w in self.dirs:
            for d in sorted(self.dirs[w]):
                if d not in self.scope:
                    self.scope.append(d)
            hit = True
        g = self.g
        for n in g.nodes:
            if n.kind in ("function", "class") and "decl" not in n.flags.split(","):
                if _word_hits_segment(w, segments(n.name)):
                    self.add_word(n.id, "word " + w)
                    hit = True
        for (fn, line, text) in g.texts:
            if re.search(r"(?<!\w)" + re.escape(w), norm(text)):
                self.add_word(fn, "word %s in literal" % w, line)
                hit = True
        for cap in self.caption_targets():
            if re.search(r"(?<!\w)" + re.escape(w) + r"(?!\w)", cap[0]):
                for fn in self.handlers_of_id(cap[2]):
                    self.add_word(fn, "word %s in caption" % w)
                    hit = True
        return hit

    # ---- helpers ----
    def in_scope(self, node):
        n = self.g.nodes[node]
        if not self.scope or not (0 <= n.file < len(self.g.files)):
            return True
        p = self.g.files[n.file].path
        return any(p.startswith(d + "/") for d in self.scope)

    def suggest(self, t):
        v = t.value
        if t.kind == "qualified":
            pool = sorted(set(self.funcs_by_qname) | {self.g.nodes[c].qname for lst in self.classes_by_name.values()
                                                      for c in lst} | set(self.ref_targets))
        else:
            pool = sorted(set(self.funcs_by_name) | set(self.classes_by_name)
                          | {x.split("::")[-1] for x in self.ref_targets})
        m = difflib.get_close_matches(v, pool, n=5, cutoff=0.6)
        if not m:
            low = {p.lower(): p for p in pool}
            m = [low[x] for x in difflib.get_close_matches(v.lower(), sorted(low), n=5, cutoff=0.6)]
        if m:
            self.suggestions[v] = m

    def run(self, terms):
        handlers = {"anchor": self.t_anchor, "path": self.t_path, "qualified": self.t_qualified,
                    "ident": self.t_ident, "id": self.t_id, "quoted": self.t_quoted, "word": self.t_word}
        # paths first so scope is known before idents with many definitions are split
        order = sorted(terms, key=lambda t: 0 if t.kind in ("path", "anchor") else 1)  # stable
        for t in terms:  # captions inside quoted text are handled by t_quoted, not as free text
            if t.kind == "quoted":
                self.qtext = self.qtext.replace(norm(t.value), " ")
        for t in order:
            ok = handlers[t.kind](t)
            if not ok and t.kind != "word":
                self.unmatched.append(t)
                if t.kind in ("ident", "qualified"):
                    self.suggest(t)
        self.captions_in_text()
        return SeedResult(self.seeds, self.exact, self.pinned, self.scope, self.focus, self.file_focus,
                          self.unmatched, self.suggestions, self.texts)


def seed(graph, terms, scope_dirs=(), query_text=""):
    return _Seeder(graph, scope_dirs, query_text).run(terms)
