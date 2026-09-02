"""Author tool: render the codelab's STAGE pictures from the REAL workflow
objects in this repo - never hand-drawn.

  1 the fan-out   stage1_fanout   the research department, drawn
  2 the pause     stage2_pause    + topic desk + the human door
  3 the script    stage3_script   the COMPLETE lap graph
  4 the gates     stage4_gates    the publish decision core, on a test bench

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


READERS = {"scan_trends": (1, 0), "read_memory": (1, 1),
           "read_backcatalog": (1, 2), "read_graph": (1, 3)}
READER_KINDS = {n: "read" for n in READERS}
READER_SUBS = {"scan_trends": "the control group — data on day 1",
               "read_memory": "honest empty until 🧠",
               "read_backcatalog": "fills after lap 1 publishes",
               "read_graph": "honest empty until 🌍"}


def main():
    from stage1_fanout.agent import root_agent as s1
    from stage2_pause.agent import root_agent as s2
    from stage3_script.agent import root_agent as s3
    from stage4_gates.agent import root_agent as s4
    from agent.post import wf_post

    (OUT / "stage-1-fanout.svg").write_text(svg(
        dump(s1), {"__START__": (0, 1.5), **READERS,
                   "join_research": (2, 1.5), "compose_bundle": (3, 1.5)},
        "stage 1 · the research department — adk web app `stage1_fanout`",
        kinds={**READER_KINDS, "join_research": "join"},
        subs={**READER_SUBS, "join_research": "holds for all four",
              "compose_bundle": "one bundle out"}, routes=False))

    (OUT / "stage-2-pause.svg").write_text(svg(
        dump(s2), {"__START__": (0, 1.5), **READERS,
                   "join_research": (2, 1.5), "compose_bundle": (3, 1.5),
                   "topic_gate": (4, 1.5), "creative_gate": (5, 1.5),
                   "persist_prefs": (6, 1.5)},
        "stage 2 · + the topic desk and the human door — adk web app `stage2_pause`",
        kinds={**READER_KINDS, "join_research": "join", "topic_gate": "agent",
               "creative_gate": "human"},
        subs={"topic_gate": "one call, a typed Brief",
              "creative_gate": "the run STOPS here",
              "persist_prefs": "your choices, into state"}, routes=False,
        cell_w=210))

    (OUT / "stage-3-script.svg").write_text(svg(
        dump(s3), {"__START__": (0, 1.5), **READERS,
                   "join_research": (2, 1.5), "compose_bundle": (3, 1.5),
                   "topic_gate": (4, 1.5), "creative_gate": (5, 1.5),
                   "persist_prefs": (6, 1.5), "scripter": (7, 1.5),
                   "store_script": (8, 1.5)},
        "stage 3 · the COMPLETE lap graph — the edge list you will write at the EDGES hole",
        kinds={**READER_KINDS, "join_research": "join", "topic_gate": "agent",
               "creative_gate": "human", "scripter": "agent"},
        subs={"scripter": "writes the 3-shot script",
              "store_script": "files it, with citations"}, routes=False,
        cell_w=200))

    (OUT / "stage-4-gates.svg").write_text(svg(
        dump(s4), {"__START__": (0, 1), "try_title": (1, 1), "policy_check": (2, 1),
                   "eval_gate": (3, 0.4), "quarantine": (3, 1.8),
                   "hold_for_publish": (4, 0), "rejected": (4, 1)},
        "stage 4 · the publish decision core, on a test bench — adk web app `stage4_gates`",
        kinds={"try_title": "harness", "hold_for_publish": "harness"},
        subs={"try_title": "your typed title, under test",
              "policy_check": "reads policy_words.txt NOW",
              "eval_gate": "3 conduct checks",
              "hold_for_publish": "publisher's seat, filled at publish"},
        cell_w=300))

    (OUT / "shape-4-post.svg").write_text(svg(
        dump(wf_post), {"__START__": (0, 1), "editor": (1, 1), "policy_check": (2, 1),
                        "eval_gate": (3, 0.4), "quarantine": (3, 2), "publisher": (4, 0),
                        "rejected": (4, 1)},
        "the same gates, for real — agent/post.py, the workflow that ships your video",
        subs={"editor": "cuts the shots", "policy_check": "reads policy_words.txt",
              "eval_gate": "3 conduct checks", "publisher": "the side effect"},
        cell_w=300))
    print("wrote 4 stage svgs + shape-4-post")


if __name__ == "__main__":
    main()
