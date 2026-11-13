"""Rank graph nodes around explore seeds and find the main flow ("spine") between them.

Interface:
    rank(graph, seeds, scope_dirs=()) -> (scores, spine)
      seeds   {node: weight} or {node: (weight, reason)} (explore_seed.SeedResult.seeds)
      scores  {node: float}  personalised PageRank mass, scope- and spine-adjusted (only nodes reached)
      spine   list[list[node]]  call-direction paths between top seeds (and, for a lone seed, the path
              from its nearest UI / message-handler entry), longest first, no path contained in another

Design (why):
  * Sub-graph = nodes within RADIUS=3 undirected steps of any seed. Bugs live within a few hops of what the
    developer named; going further mostly adds generic utilities.
  * Edges walked: calls (both ways), handled_by, triggers, sends, overrides, binds, uses_dialog, contains,
    plus a virtual class<->method edge (weight MEMBER_W) so a class seed spreads to its own methods.
    External nodes (MFC/Win32, unresolved) are never entered: they have no code to show and would act as hubs.
  * Edge weight by resolution confidence: exact 1, likely 0.7, heuristic 0.5, ambiguous 0.3/n (n candidates of
    that call site) — uncertain edges should carry proportionally less relevance.
  * Personalised PageRank (random walk with restart RESTART=0.3, ITERATIONS=20) from the seed weights: a node
    scores high when many strong short paths connect it to seeds, which is what "related code" means.
    Mass of nodes with no admissible neighbour returns to the restart vector.
  * Scope: nodes in files outside scope_dirs are multiplied by OUT_OF_SCOPE=0.2 (kept, but rarely shown).
  * Spine: shortest call-direction path (<= MAX_PATH steps) between every ordered pair of the top TOP_SEEDS
    function seeds; MFC hops count as forward (UI -> ID -> handler, sender -> message ID -> handler).
    Spine nodes get x SPINE_BOOST: the path between named things is usually the answer.
"""
from collections import deque

RADIUS = 3
RESTART = 0.3
ITERATIONS = 20
OUT_OF_SCOPE = 0.2
SPINE_BOOST = 2.0
TOP_SEEDS = 4
MAX_PATH = 6
MEMBER_W = 0.3

CONF_W = {"exact": 1.0, "likely": 0.7, "heuristic": 0.5, "ambiguous": 0.3, "": 1.0}
WALK_KINDS = frozenset(["calls", "handled_by", "triggers", "sends", "overrides", "binds", "uses_dialog", "contains"])
# forward (call-direction) kinds for the spine: src -> dst
FORWARD_KINDS = frozenset(["calls", "handled_by", "triggers", "sends"])


def _weight(seeds, n):
    v = seeds[n]
    return float(v[0] if isinstance(v, tuple) else v)


def _edge_weights(g):
    """Return {(a, b): w} undirected admissible edges (max weight if several)."""
    cached = getattr(g, "_explore_adj", None)
    if cached is not None:
        return cached
    nodes = g.nodes
    amb = {}
    for e in g.edges:
        if e.kind == "calls" and e.conf == "ambiguous":
            amb[(e.src, e.file, e.line)] = amb.get((e.src, e.file, e.line), 0) + 1
    adj = [dict() for _ in nodes]

    def link(a, b, w):
        if w <= 0 or a == b:
            return
        if adj[a].get(b, 0) < w:
            adj[a][b] = w
        if adj[b].get(a, 0) < w:
            adj[b][a] = w

    for e in g.edges:
        if e.kind not in WALK_KINDS or e.conf == "external":
            continue
        if nodes[e.src].kind == "external" or nodes[e.dst].kind == "external":
            continue
        w = CONF_W.get(e.conf, 0.5)
        if e.conf == "ambiguous":
            w /= max(1, amb.get((e.src, e.file, e.line), 1))
        link(e.src, e.dst, w)
    for n in nodes:
        if n.kind == "function" and n.owner >= 0:
            link(n.id, n.owner, MEMBER_W)
    g._explore_adj = adj
    return adj


def _forward(g):
    cached = getattr(g, "_explore_fwd", None)
    if cached is not None:
        return cached
    nodes = g.nodes
    fwd = [[] for _ in nodes]
    for e in g.edges:
        if e.kind in FORWARD_KINDS and e.conf != "external" and nodes[e.dst].kind != "external":
            fwd[e.src].append(e.dst)
    for lst in fwd:
        lst.sort()
    g._explore_fwd = fwd
    return fwd


def subgraph(g, seeds, radius=RADIUS):
    adj = _edge_weights(g)
    dist = {s: 0 for s in seeds}
    q = deque(sorted(seeds))
    while q:
        u = q.popleft()
        if dist[u] >= radius:
            continue
        for v in sorted(adj[u]):
            if v not in dist:
                dist[v] = dist[u] + 1
                q.append(v)
    return dist


def ppr(g, seeds, members):
    adj = _edge_weights(g)
    total = sum(_weight(seeds, s) for s in seeds) or 1.0
    restart = {s: _weight(seeds, s) / total for s in seeds}
    out_w = {u: sum(w for v, w in adj[u].items() if v in members) for u in members}
    p = dict(restart)
    for _ in range(ITERATIONS):
        nxt = {s: RESTART * r for s, r in restart.items()}
        lost = 0.0
        for u in sorted(p):
            mass = p[u] * (1.0 - RESTART)
            ow = out_w.get(u, 0.0)
            if ow <= 0:
                lost += mass
                continue
            for v, w in adj[u].items():
                if v in members:
                    nxt[v] = nxt.get(v, 0.0) + mass * w / ow
        if lost:
            for s, r in restart.items():
                nxt[s] = nxt.get(s, 0.0) + lost * r
        p = nxt
    return p


def in_scope(g, n, scope_dirs):
    node = g.nodes[n]
    if not scope_dirs or not (0 <= node.file < len(g.files)):
        return True
    path = g.files[node.file].path
    return any(path.startswith(d.rstrip("/") + "/") for d in scope_dirs)


def shortest_path(g, a, b, max_len=MAX_PATH):
    fwd = _forward(g)
    prev = {a: None}
    q = deque([(a, 0)])
    while q:
        u, d = q.popleft()
        if u == b:
            break
        if d >= max_len:
            continue
        for v in fwd[u]:
            if v not in prev:
                prev[v] = u
                q.append((v, d + 1))
    if b not in prev:
        return None
    path = [b]
    while prev[path[-1]] is not None:
        path.append(prev[path[-1]])
    return path[::-1]


def entry_path(g, target, max_len=MAX_PATH):
    """Shortest reverse path from target to a UI item, message handler or framework entry (as a forward path)."""
    nodes = g.nodes
    inn = {}
    fwd = _forward(g)
    for u, lst in enumerate(fwd):
        for v in lst:
            inn.setdefault(v, []).append(u)
    prev = {target: None}
    q = deque([(target, 0)])
    found = None
    while q:
        u, d = q.popleft()
        fl = nodes[u].flags.split(",")
        if u != target and (nodes[u].kind == "ui" or "msg-handler" in fl or "framework-entry" in fl):
            found = u
            break
        if nodes[u].kind == "ui" or d >= max_len:
            continue
        for v in sorted(inn.get(u, ())):
            if v not in prev:
                prev[v] = u
                q.append((v, d + 1))
    if found is None:
        return None
    path = [found]
    while prev[path[-1]] is not None:
        path.append(prev[path[-1]])
    return path


def _contained(p, q):
    """True if path p is a contiguous part of path q."""
    if len(p) > len(q):
        return False
    for i in range(len(q) - len(p) + 1):
        if q[i:i + len(p)] == p:
            return True
    return False


def find_spine(g, seeds):
    funcs = [s for s in seeds if g.nodes[s].kind == "function"]
    funcs.sort(key=lambda s: (-_weight(seeds, s), s))
    top = funcs[:TOP_SEEDS]
    paths = []
    for a in top:
        for b in top:
            if a != b:
                p = shortest_path(g, a, b)
                if p and len(p) > 1:
                    paths.append(p)
    if not paths and top:
        p = entry_path(g, top[0])
        if p and len(p) > 1:
            paths.append(p)
    paths.sort(key=lambda p: (-len(p), p))
    out = []
    for p in paths:
        if not any(_contained(p, q) for q in out):
            out.append(p)
    return out


def rank(g, seeds, scope_dirs=()):
    if not seeds:
        return {}, []
    members = subgraph(g, seeds)
    scores = ppr(g, seeds, members)
    spine = find_spine(g, seeds)
    on_spine = {n for p in spine for n in p}
    for n in list(scores):
        if not in_scope(g, n, scope_dirs):
            scores[n] *= OUT_OF_SCOPE
        if n in on_spine:
            scores[n] *= SPINE_BOOST
    for n in on_spine:
        scores.setdefault(n, 0.0)
    return scores, spine
