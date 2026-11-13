"""Parse an mfc_explore query into typed terms. No dependency on the rest of mfcgraph.

Interface:
    parse_query(text) -> list[Term]
    Term(kind, value, extra) with kind in KINDS:
      anchor     "File.cpp:120" / "Dir\\File.cpp:100-140"   value = path ("/" separators), extra = (start, end)
      path       token with "/" or "\\", or a source-file extension     value = path, extra = "file" | "dir"
      qualified  "A::B" (also "A.B" when A is PascalCase)              value = "A::B", extra = ""
      id         ID_ IDD_ IDC_ IDS_ IDR_ IDM_ WM_ UWM_ + upper case    value = token
      quoted     text inside "..." '...' “...” ‘...’ (kept verbatim)  value = text
      ident      CamelCase, contains "_", or starts with m_            value = token
      word       anything else, lower-cased (NFC), stopwords removed   value = word
Terms keep query order; duplicates (same kind and value) are dropped.
"""
import re
import unicodedata
from collections import namedtuple

Term = namedtuple("Term", "kind value extra")
KINDS = ("anchor", "path", "qualified", "id", "quoted", "ident", "word")

SOURCE_EXTS = ("cpp", "cxx", "cc", "c", "h", "hpp", "hxx", "hh", "inl", "ipp", "rc", "rc2", "dlg")
_EXT = "|".join(SOURCE_EXTS)
_RE_ANCHOR = re.compile(r"^(.+\.(?:%s)):(\d+)(?:\s*-\s*(\d+))?$" % _EXT, re.I)
_RE_FILE = re.compile(r"\.(?:%s)$" % _EXT, re.I)
_RE_ID = re.compile(r"^(?:ID|IDD|IDC|IDS|IDR|IDM|WM|UWM)_[A-Z0-9_]+$")
_RE_IDENT_CHARS = re.compile(r"^[A-Za-z_~][A-Za-z0-9_]*$")
_RE_DOTTED = re.compile(r"^([A-Z][A-Za-z0-9_]*[a-z][A-Za-z0-9_]*)\.(~?[A-Za-z_][A-Za-z0-9_]*)$")
_RE_QUOTED = re.compile(r'"([^"]+)"|“([^”]+)”|‘([^’]+)’|(?:(?<=\s)|^)\'([^\']+)\'(?=[\s,.;:!?)]|$)')
_STRIP = ",;!?()[]{}<>“”‘’\"'"

STOPWORDS = frozenset("""
a an the and or but if then else when while of in on at to for from by with without into onto about as is are
was were be been being do does did done have has had this that these those it its there here what which who
whom whose why how where can could should would will shall may might must not no yes so too very just only
also than i me my we our you your he she they them their his her after before during up down out over under
again any all some each every more most other such own same few both between through
bug bugs issue issues problem problems wrong error errors fail fails failed failing broken incorrect happens
happen occurs occur please help find check look show see get gets got why does module function method class
code file line value values click clicks clicked press pressed button
và hoặc nhưng nếu thì khi lúc trong ngoài trên dưới của cho với từ đến là bị được có không chưa đã đang sẽ
rồi mà này kia đó ấy các những một hai cái chiếc vào ra lên xuống lại nữa cũng vẫn còn rất quá hơn nhất
thế nào sao gì đâu ai bao nhiêu tại vì do nên để hãy giúp tìm xem kiểm tra lỗi sai hỏng bấm nhấn chọn nút
hàm lớp file dòng mã code chỗ phần hiện hiển thị thấy bug module
""".split())


def _norm(s):
    return unicodedata.normalize("NFC", s)


def _is_camel(tok):
    # at least one lower->upper transition, e.g. OnFileExport, exportCsv, CExportDlg
    return re.search(r"[a-z0-9][A-Z]", tok) is not None or re.match(r"^[A-Z]{2,}[a-z]", tok) is not None


def _classify(tok):
    m = _RE_ANCHOR.match(tok)
    if m:
        a = int(m.group(2))
        b = int(m.group(3)) if m.group(3) else a
        return Term("anchor", m.group(1).replace("\\", "/"), (min(a, b), max(a, b)))
    if "/" in tok or "\\" in tok:
        p = tok.replace("\\", "/")
        return Term("path", p.rstrip("/") if not _RE_FILE.search(p) else p, "file" if _RE_FILE.search(p) else "dir")
    if _RE_FILE.search(tok) and _RE_IDENT_CHARS.match(tok.split(".")[0] or "x"):
        return Term("path", tok, "file")
    if "::" in tok:
        parts = [x for x in tok.split("::")]
        if all(_RE_IDENT_CHARS.match(x) for x in parts if x) and any(parts):
            return Term("qualified", tok.strip(":"), "")
    m = _RE_DOTTED.match(tok)
    if m:
        return Term("qualified", m.group(1) + "::" + m.group(2), "")
    if _RE_ID.match(tok):
        return Term("id", tok, "")
    if _RE_IDENT_CHARS.match(tok) and (_is_camel(tok) or "_" in tok.strip("_") or tok.startswith("m_")):
        return Term("ident", tok, "")
    w = tok.lower()
    if len(w) < 2 or w in STOPWORDS or w.isdigit():
        return None
    return Term("word", w, "")


def _split_word_token(tok):
    """'tiền,' -> ['tiền']; 'Export...' -> ['Export']; keeps ':' '.' '/' '\\' needed by anchors/paths."""
    tok = tok.strip(_STRIP)
    tok = tok.rstrip(".:")
    if not tok:
        return []
    if "/" in tok or "\\" in tok or "::" in tok or _RE_ANCHOR.match(tok) or _RE_FILE.search(tok):
        return [tok]
    if _RE_DOTTED.match(tok):
        return [tok]
    # split remaining punctuation inside words ("tổng/tiền" handled above as path; "a.b" lower-case -> two words)
    return [x for x in re.split(r"[^\w~]+", tok) if x]


def parse_query(text):
    text = _norm(text or "")
    terms = []   # (position in text, Term) so the result keeps query order
    chunks = []  # unquoted parts: (offset, text)
    pos = 0
    for m in _RE_QUOTED.finditer(text):
        chunks.append((pos, text[pos:m.start()]))
        q = next(g for g in m.groups() if g is not None).strip()
        if q:
            terms.append((m.start(), Term("quoted", q, "")))
        pos = m.end()
    chunks.append((pos, text[pos:]))
    for base, chunk in chunks:
        for m in re.finditer(r"\S+", chunk):
            for tok in _split_word_token(m.group(0)):
                t = _classify(tok)
                if t is not None:
                    terms.append((base + m.start(), t))
    terms.sort(key=lambda x: x[0])
    out, seen = [], set()
    for _, t in terms:
        key = (t.kind, t.value)
        if key not in seen:
            seen.add(key)
            out.append(t)
    return out
