"""The live map of the workflow - dumped from the REAL object, lit by the run.

Two rules, borrowed from the same grammar the rest of Annie's stages use:

  1 · The structure is never hand-drawn. Nodes and edges come from
      `wf.graph.edges` (each Edge carries from_node.name / to_node.name), so
      the map cannot drift from the code the student just read. The layout
      table only says WHERE to put a node; a node the table forgot still
      renders, in a tray at the bottom - the map may be ugly, it may not lie.

  2 · Every lit state is read from real run artifacts (runs/state.json and
      the lap's phase). Nothing is animated on a timer.

And one flourish: the marker that walks the graph is the avatar the student
generated in chapter 2, so the face on the map is theirs.
"""
from agent import state as _state

# where each node sits (grid units) - layout only, never structure
LAYOUT = {
    "__START__":        (0, 1.5),
    "scan_trends":      (1, 0),
    "read_memory":      (1, 1),
    "read_backcatalog": (1, 2),
    "read_graph":       (1, 3),
    "join_research":    (2, 1.5),
    "compose_bundle":   (3, 1.5),
    "topic_gate":       (4, 1.5),
    # the tail wraps onto a second row so the map stays readable
    "creative_gate":    (1, 4.6),
    "persist_prefs":    (2, 4.6),
    "scripter":         (3, 4.6),
    "store_script":     (4, 4.6),
}
SUB = {
    "scan_trends": "what the room watches",
    "read_memory": "what you learned",
    "read_backcatalog": "your own wall",
    "read_graph": "the audience graph",
    "join_research": "waits for all 4",
    "compose_bundle": "one cited bundle",
    "topic_gate": "picks the topic",
    "creative_gate": "your form",
    "persist_prefs": "user:prefs",
    "scripter": "3 shots, typed",
    "store_script": "the ledger",
}
HUMAN = {"creative_gate"}          # the node that pauses FOR you

CELL_W, CELL_H, PAD = 168, 76, 26
BOX_W, BOX_H = 146, 50
INK, SUBC, LINE = "#2B2320", "#8B7E70", "#D9CFC0"
DONE, NOW, HUMANC = "#C96442", "#E9B44C", "#E9B44C"


def graph_edges() -> list[tuple[str, str]]:
    """The real thing, or a readable fallback if a hole is still open."""
    try:
        from agent.graph import wf
        return [(e.from_node.name, e.to_node.name) for e in wf.graph.edges]
    except Exception:
        order = list(LAYOUT)
        return [("__START__", n) for n in order[1:5]] + [
            (n, "join_research") for n in order[1:5]] + [
            ("join_research", "compose_bundle"), ("compose_bundle", "topic_gate"),
            ("topic_gate", "creative_gate"), ("creative_gate", "persist_prefs"),
            ("persist_prefs", "scripter"), ("scripter", "store_script")]


def node_states(st: dict, phase: str) -> dict[str, str]:
    """done · now · you · idle - each one read from what the run actually wrote."""
    past = phase in ("proposal", "form", "scripted", "published")
    researched = bool(st.get("graph_report") or st.get("memory_facts") or past)
    bundled = bool(st.get("brief")) or past
    chose = bool(st.get("choices"))
    scripted = bool(st.get("script"))
    s = {}
    for n in LAYOUT:
        if n == "__START__":
            s[n] = "done" if st.get("run_id") else "idle"
        elif n in ("scan_trends", "read_memory", "read_backcatalog", "read_graph"):
            s[n] = "done" if researched else "now"
        elif n in ("join_research", "compose_bundle"):
            s[n] = "done" if bundled else ("now" if researched else "idle")
        elif n == "topic_gate":
            passed = chose or scripted or phase in ("form", "scripted", "published")
            s[n] = "done" if passed else ("now" if bundled else "idle")
        elif n == "creative_gate":
            passed = chose or scripted or phase in ("scripted", "published")
            s[n] = "done" if passed else ("you" if phase == "form" else "idle")
        elif n == "persist_prefs":
            s[n] = "done" if chose else "idle"
        else:
            s[n] = "done" if scripted else ("now" if chose else "idle")
    return s


def marker_node(states: dict[str, str]) -> str:
    """Where YOUR face stands: the node the run is at right now."""
    for n in LAYOUT:
        if states.get(n) in ("you", "now"):
            return n
    done = [n for n in LAYOUT if states.get(n) == "done"]
    return done[-1] if done else "__START__"


def _xy(node: str) -> tuple[float, float]:
    col, row = LAYOUT[node]
    return PAD + col * CELL_W + BOX_W / 2, PAD + row * CELL_H + BOX_H / 2


def render(st: dict, phase: str, avatar_url: str) -> str:
    edges, states = graph_edges(), node_states(st, phase)
    width = PAD * 2 + (max(c for c, _ in LAYOUT.values())) * CELL_W + BOX_W
    height = PAD * 2 + (max(r for _, r in LAYOUT.values())) * CELL_H + BOX_H + 10
    parts = [f'<svg viewBox="0 0 {width:.0f} {height:.0f}" width="100%" '
             f'style="max-width:{width:.0f}px;display:block;margin:0 auto">']

    for a, b in edges:                                   # edges first, under the boxes
        if a not in LAYOUT or b not in LAYOUT:
            continue
        (x1, y1), (x2, y2) = _xy(a), _xy(b)
        x1 += BOX_W / 2 if a != "__START__" else 26
        x2 -= BOX_W / 2
        lit = states.get(a) == "done" and states.get(b) in ("done", "now", "you")
        mid = (x1 + x2) / 2
        parts.append(f'<path d="M{x1:.0f},{y1:.0f} C{mid:.0f},{y1:.0f} {mid:.0f},{y2:.0f} '
                     f'{x2:.0f},{y2:.0f}" fill="none" stroke="{DONE if lit else LINE}" '
                     f'stroke-width="{2.5 if lit else 2}"/>')

    for node, kind in states.items():
        cx, cy = _xy(node)
        if node == "__START__":
            parts.append(f'<circle cx="{cx:.0f}" cy="{cy:.0f}" r="20" '
                         f'fill="{DONE if kind == "done" else "#fff"}" stroke="{DONE}" '
                         f'stroke-width="2"/>'
                         f'<text x="{cx:.0f}" y="{cy + 4:.0f}" text-anchor="middle" '
                         f'font-size="9.5" font-family="SF Mono,Menlo,monospace" '
                         f'fill="{"#fff" if kind == "done" else DONE}">START</text>')
            continue
        x, y = cx - BOX_W / 2, cy - BOX_H / 2
        fill, stroke, txt = "#fff", LINE, SUBC
        if kind == "done":
            fill, stroke, txt = "#FDF3EC", DONE, INK
        elif kind == "now":
            fill, stroke, txt = "#FFF8E9", NOW, INK
        elif kind == "you":
            fill, stroke, txt = "#FFF8E9", HUMANC, INK
        halo = (f'<rect x="{x - 4:.0f}" y="{y - 4:.0f}" width="{BOX_W + 8}" '
                f'height="{BOX_H + 8}" rx="14" fill="none" stroke="{HUMANC}" '
                f'stroke-width="2" opacity=".35"/>') if kind in ("now", "you") else ""
        badge = (f'<text x="{x + BOX_W - 8:.0f}" y="{y + 13:.0f}" text-anchor="end" '
                 f'font-size="8.5" font-family="SF Mono,Menlo,monospace" '
                 f'fill="#B4802A">YOU</text>') if kind == "you" else ""
        parts.append(
            f'{halo}<rect x="{x:.0f}" y="{y:.0f}" width="{BOX_W}" height="{BOX_H}" rx="11" '
            f'fill="{fill}" stroke="{stroke}" stroke-width="2"/>{badge}'
            f'<text x="{cx:.0f}" y="{y + 22:.0f}" text-anchor="middle" font-size="12.5" '
            f'font-family="SF Mono,Menlo,monospace" fill="{txt}">{node}</text>'
            f'<text x="{cx:.0f}" y="{y + 37:.0f}" text-anchor="middle" font-size="10" '
            f'fill="{SUBC}">{SUB.get(node, "")}</text>')

    mx, my = _xy(marker_node(states))                    # E · your face, on the map
    parts.append(
        f'<defs><clipPath id="me"><circle cx="{mx:.0f}" cy="{my - BOX_H / 2 - 16:.0f}" '
        f'r="15"/></clipPath></defs>'
        f'<circle cx="{mx:.0f}" cy="{my - BOX_H / 2 - 16:.0f}" r="17" fill="#fff" '
        f'stroke="{DONE}" stroke-width="2"/>'
        f'<image href="{avatar_url}" x="{mx - 15:.0f}" y="{my - BOX_H / 2 - 31:.0f}" '
        f'width="30" height="30" clip-path="url(#me)"/>')
    parts.append("</svg>")

    missing = [n for pair in edges for n in pair if n not in LAYOUT]
    tray = (f'<div class="h0s" style="margin-top:6px">unplaced nodes: '
            f'{", ".join(sorted(set(missing)))}</div>' if missing else "")
    return (f'<div class="flow">{"".join(parts)}{tray}</div>')


def strip(avatar_url: str) -> str:
    st = _state.load()
    try:
        from agent import lap
        phase = lap.where().get("phase", "")
    except Exception:
        phase = ""
    return render(st, phase, avatar_url)
