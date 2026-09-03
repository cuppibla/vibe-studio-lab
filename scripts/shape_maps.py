"""Author tool: render the codelab's STAGE pictures from the REAL workflow
objects in this repo - never hand-drawn.

  1 the fan-out    stage1_fanout     the research department, drawn (2 readers)
  2 the direction  stage2_direction  + 3 candidates in state + the human door
  3 the router     stage3_router     + the policy gate = the complete base graph

Run: python scripts/shape_maps.py     (writes codelab-img/stage-*.svg)
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
        "join":   ("#F6F1E8", "#C9BCA9", INK, ""),
        "human":  ("#FFF8E9", "#B4802A", INK, "⏸ "),
        "harness": ("#F3F1EE", "#B9AFA2", SUB, "⚙ ")}


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


READERS = {"scan_trends": (1, 0), "read_backcatalog": (1, 1)}
READER_KINDS = {n: "read" for n in READERS}
READER_SUBS = {"scan_trends": "what the room watches",
               "read_backcatalog": "fills after your first publish"}


def main():
    from stage1_fanout.agent import root_agent as s1
    from stage2_direction.agent import root_agent as s2
    from stage3_router.agent import root_agent as s3
    from agent.post import wf_post

    (OUT / "stage-1-fanout.svg").write_text(svg(
        dump(s1), {"__START__": (0, 0.5), **READERS,
                   "join_research": (2, 0.5), "compose_bundle": (3, 0.5)},
        "stage 1 · the research department — adk web app `stage1_fanout` (two readers, for now)",
        kinds={**READER_KINDS, "join_research": "join"},
        subs={**READER_SUBS, "join_research": "waits for every wired feed",
              "compose_bundle": "one bundle out"}, routes=False))

    (OUT / "stage-2-direction.svg").write_text(svg(
        dump(s2), {"__START__": (0, 0.5), **READERS,
                   "join_research": (2, 0.5), "compose_bundle": (3, 0.5),
                   "propose_directions": (4, 0.5), "direction_gate": (5, 0.5),
                   "persist_direction": (6, 0.5)},
        "stage 2 · three candidates, then the human door — adk web app `stage2_direction`",
        kinds={**READER_KINDS, "join_research": "join",
               "propose_directions": "agent", "direction_gate": "human"},
        subs={"propose_directions": "3 candidates, into state",
              "direction_gate": "pick 1 / 2 / 3 — the run STOPS",
              "persist_direction": "your pick, resolved"}, routes=False,
        cell_w=214))

    (OUT / "stage-3-router.svg").write_text(svg(
        dump(s3), {"__START__": (0, 0.7), **READERS,
                   "join_research": (2, 0.7), "compose_bundle": (3, 0.7),
                   "propose_directions": (4, 0.7), "direction_gate": (5, 0.7),
                   "persist_direction": (6, 0.7), "policy_check": (7, 0.7),
                   "scripter": (8, 0.2), "quarantine": (8, 1.6),
                   "store_script": (9, 0.2)},
        "stage 3 · the policy gate, before any money — adk web app `stage3_router`",
        kinds={**READER_KINDS, "join_research": "join",
               "propose_directions": "agent", "direction_gate": "human",
               "scripter": "agent"},
        subs={"policy_check": "reads policy_words.txt NOW",
              "quarantine": "the polite stop",
              "scripter": "runs quietly"},
        cell_w=196))

    (OUT / "shape-4-post.svg").write_text(svg(
        dump(wf_post), {"__START__": (0, 0.7), "editor": (1, 0.7),
                        "eval_gate": (2, 0.7), "publisher": (3, 0),
                        "rejected": (3, 1.4)},
        "the publish backstop — agent/post.py, one eval in front of the side effect",
        subs={"editor": "cuts the shots", "eval_gate": "3 conduct checks",
              "publisher": "the side effect"},
        cell_w=330))
    print("wrote 3 stage svgs + shape-4-post")


if __name__ == "__main__":
    main()
