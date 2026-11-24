"""Remembered index settings: <root>/.mfcgraph/settings.json (written next to the index, nowhere else).

Interface:
    CONFIG_OPTIONS            index options that are settings (--codepage --exclude --define --undef --undef-unknown
                              --vcxproj --config --vcxproj-scope)
    settings_path(root) -> str
    from_args(a, root) -> dict          the settings in parsed CLI args (`cli._parse` dict); .vcxproj paths under root
                                        are stored relative to it (forward slashes), so the folder can move
    apply(settings, a, root)            write saved settings into parsed CLI args (relative paths resolved)
    load(root) -> dict | None           None if missing or unreadable (a broken file never stops index)
    save(root, settings) -> path
    describe(settings) -> str           one line for the console / GUI
`index <root>` with no CONFIG_OPTIONS reuses the saved settings; with any of them the settings are exactly those
options (no hidden merge) and are saved again after a successful index.
"""
import io
import json
import os

FORMAT = 1
CONFIG_OPTIONS = ("--codepage", "--exclude", "--define", "--undef", "--undef-unknown", "--vcxproj", "--config",
                  "--vcxproj-scope")
DEFAULTS = {"codepage": 1258, "exclude": "", "define": "", "undef": "", "undef_unknown": False, "vcxproj": [],
            "config": "", "vcxproj_scope": ""}


def settings_path(root):
    return os.path.join(os.path.abspath(root), ".mfcgraph", "settings.json")


def _split(text):
    return [x.strip() for x in (text or "").split(";") if x.strip()]


def _rel(path, root):
    path = os.path.abspath(path)
    try:
        rel = os.path.relpath(path, root)
    except ValueError:  # other drive on Windows
        return path
    if rel == os.pardir or rel.startswith(os.pardir + os.sep):
        return path
    return rel.replace(os.sep, "/")


def from_args(a, root):
    root = os.path.abspath(root)
    s = dict(DEFAULTS)
    for k in ("codepage", "exclude", "define", "undef", "undef_unknown", "config", "vcxproj_scope"):
        s[k] = a.get(k, DEFAULTS[k])
    s["vcxproj"] = [_rel(p, root) for p in _split(a.get("vcxproj", ""))]
    return s


def apply(settings, a, root):
    root = os.path.abspath(root)
    for k in ("codepage", "exclude", "define", "undef", "undef_unknown", "config", "vcxproj_scope"):
        a[k] = settings.get(k, DEFAULTS[k])
    paths = [p if os.path.isabs(p) else os.path.normpath(os.path.join(root, p.replace("/", os.sep)))
             for p in settings.get("vcxproj", [])]
    a["vcxproj"] = ";".join(paths)


def load(root):
    path = settings_path(root)
    try:
        with io.open(path, encoding="utf-8") as f:
            data = json.load(f)
    except (OSError, ValueError):
        return None
    if not isinstance(data, dict):
        return None
    s = dict(DEFAULTS)
    for k, default in DEFAULTS.items():
        v = data.get(k, default)
        if type(v) is type(default):  # exact type: a bool is not a codepage
            s[k] = v
    s["vcxproj"] = [p for p in s["vcxproj"] if isinstance(p, str)]
    return s


def save(root, settings):
    path = settings_path(root)
    d = os.path.dirname(path)
    if not os.path.isdir(d):
        os.makedirs(d)
    data = dict(settings)
    data["format"] = FORMAT
    with io.open(path, "w", encoding="utf-8", newline="\n") as f:
        f.write(json.dumps(data, indent=1, sort_keys=True, ensure_ascii=False) + "\n")
    return path


def describe(s):
    parts = ["codepage %s" % s.get("codepage")]
    if s.get("vcxproj"):
        parts.append("projects %s" % "; ".join(s["vcxproj"]))
        parts.append("config %s" % (s.get("config") or "default"))
        if s.get("vcxproj_scope"):
            parts.append("scope %s" % s["vcxproj_scope"])
    for k, label in (("define", "define"), ("undef", "undef"), ("exclude", "exclude")):
        if s.get(k):
            parts.append("%s %s" % (label, s[k]))
    if s.get("undef_unknown"):
        parts.append("undef-unknown")
    return ", ".join(parts)
