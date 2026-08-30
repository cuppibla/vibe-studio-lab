"""Author tool: render the codelab's SHAPE pictures from the REAL workflow
objects in this repo - never hand-drawn.

  1 a line     shape1_line     the two-node sandbox the student runs
  2 a router   shape2_router   one node, two exits
  3 a fan-out  shape3_fanout   3 readers, a join, an agent node, a nested workflow
  4 the real router            agent/post.py - the same shape, doing the shipping

Run: python scripts/shape_maps.py     (writes codelab-img/shape-*.svg)
"""
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

OUT = ROOT / "codelab-img"
INK, SUB, EDGE, DONE, AMBER = "#2B2320", "#8B7E70", "#D9CFC0", "#C96442", "#B4802A"
BOX_W, BOX_H, CELL_W, CELL_H, PAD = 176, 60, 226, 100, 30

# fill · stroke · text · prefix, by node kind (same palette as the lab's diagrams)
KIND = {"plain":  ("#FFFFFF", "#E8DFD2", INK, ""),
        "read":   ("#EFF4EC", "#6E9A68", INK, ""),
        "agent":  ("#8B7EC8", "#8B7EC8", "#FFFFFF", "✦ "),
        "nested": ("#FBEEE8", "#C96442", INK, "⧉ "),
        "join":   ("#F6F1E8", "#C9BCA9", INK, "")}


def svg(edges, layout, caption, kinds=None, subs=None, routes=True, cell_w=CELL_W):
    kinds, subs = kinds or {}, subs or {}
    W = PAD * 2 + max(c for c, _ in layout.values()) * cell_w + BOX_W
    H = PAD * 2 + max(r for _, r in layout.values()) * CELL_H + BOX_H + 34

    def xy(n):
        c, r = layout[n]
        return PAD + c * cell_w + BOX_W / 2, PAD + r * CELL_H + BOX_H / 2

    p = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{W:.0f}" height="{H:.0f}" '
         f'viewBox="0 0 {W:.0f} {H:.0f}"><rect width="{W:.0f}" height="{H:.0f}" fill="#FAF6F0"/>']
    for a, b, route in edges:
        if a not in layout or b not in layout:
            continue
        (x1, y1), (x2, y2) = xy(a), xy(b)
        x1 += BOX_W / 2 if a != "__START__" else 24
        x2 -= BOX_W / 2
        mid = (x1 + x2) / 2
        p.append(f'<path d="M{x1:.0f},{y1:.0f} C{mid:.0f},{y1:.0f} {mid:.0f},{y2:.0f} '
                 f'{x2:.0f},{y2:.0f}" fill="none" stroke="{EDGE}" stroke-width="2.5"/>')
        if route and routes:
            p.append(f'<rect x="{mid - 27:.0f}" y="{(y1 + y2) / 2 - 13:.0f}" width="54" '
                     f'height="20" rx="7" fill="#FFF8E9" stroke="{AMBER}" stroke-width="1.6"/>'
                     f'<text x="{mid:.0f}" y="{(y1 + y2) / 2 + 1:.0f}" text-anchor="middle" '
                     f'font-size="11.5" font-family="SF Mono,Menlo,monospace" '
                     f'fill="{AMBER}">{route}</text>')
    for n in layout:
        cx, cy = xy(n)
        if n == "__START__":
            p.append(f'<circle cx="{cx:.0f}" cy="{cy:.0f}" r="22" fill="{DONE}"/>'
                     f'<text x="{cx:.0f}" y="{cy + 4:.0f}" text-anchor="middle" font-size="10" '
                     f'font-family="SF Mono,Menlo,monospace" fill="#fff">START</text>')
            continue
        fill, stroke, ink, prefix = KIND[kinds.get(n, "plain")]
        sub = subs.get(n, "")
        x, y = cx - BOX_W / 2, cy - BOX_H / 2
        dy = -3 if sub else 5
        p.append(f'<rect x="{x:.0f}" y="{y:.0f}" width="{BOX_W}" height="{BOX_H}" rx="12" '
                 f'fill="{fill}" stroke="{stroke}" stroke-width="2"/>'
                 f'<text x="{cx:.0f}" y="{cy + dy:.0f}" text-anchor="middle" font-size="14.5" '
                 f'font-family="SF Mono,Menlo,monospace" fill="{ink}">{prefix}{n}</text>')
        if sub:
            grey = "#EDE7FA" if kinds.get(n) == "agent" else SUB
            p.append(f'<text x="{cx:.0f}" y="{cy + 17:.0f}" text-anchor="middle" font-size="11.5" '
                     f'font-family="-apple-system,Arial" fill="{grey}">{sub}</text>')
    p.append(f'<text x="{PAD}" y="{H - 12:.0f}" font-size="15" fill="{SUB}" '
             f'font-family="-apple-system,Arial">{caption}</text></svg>')
    return "".join(p)


def dump(wf):
    return [(e.from_node.name, e.to_node.name, e.route) for e in wf.graph.edges]


def main():
    from shape1_line.agent import root_agent as line
    from shape2_router.agent import root_agent as router
    from shape3_fanout.agent import root_agent as fan
    from agent.post import wf_post

    (OUT / "shape-1-line.svg").write_text(svg(
        dump(line), {"__START__": (0, 0), "slugify": (1, 0), "name_the_file": (2, 0)},
        "① a line — adk web app `shape1_line`",
        subs={"slugify": "writes state['slug']", "name_the_file": "reads slug from state"},
        routes=False))

    (OUT / "shape-2-router.svg").write_text(svg(
        dump(router), {"__START__": (0, 0.5), "policy_check": (1, 0.5),
                       "publish": (2, 0), "quarantine": (2, 1)},
        "② a router — adk web app `shape2_router`",
        subs={"policy_check": "returns a route", "publish": "one exit",
              "quarantine": "the other exit"}, cell_w=330))

    (OUT / "shape-3-fanout.svg").write_text(svg(
        dump(fan), {"__START__": (0, 1), "read_trends": (1, 0), "read_memory": (1, 1),
                    "read_history": (1, 2), "join_desk": (2, 1), "pitch": (3, 1),
                    "shape2_router": (4, 1), "announce": (5, 1)},
        "③ a fan-out and a join — adk web app `shape3_fanout`",
        kinds={"read_trends": "read", "read_memory": "read", "read_history": "read",
               "join_desk": "join", "pitch": "agent", "shape2_router": "nested"},
        subs={"read_trends": "writes state['trends']", "read_memory": "writes state['memory']",
              "read_history": "writes state['history']", "join_desk": "holds for all three",
              "pitch": "an agent, as a node", "shape2_router": "shape ② as ONE node",
              "announce": "back in the outer graph"}))

    (OUT / "shape-4-post.svg").write_text(svg(
        dump(wf_post), {"__START__": (0, 1), "editor": (1, 1), "policy_check": (2, 1),
                        "eval_gate": (3, 0.4), "quarantine": (3, 2), "publisher": (4, 0),
                        "rejected": (4, 1)},
        "the same router, for real — agent/post.py, the workflow that ships your video",
        subs={"editor": "cuts the shots", "policy_check": "blacklist",
              "eval_gate": "3 conduct checks", "publisher": "the side effect"},
        cell_w=300))
    print("wrote 4 shape svgs")


if __name__ == "__main__":
    main()
