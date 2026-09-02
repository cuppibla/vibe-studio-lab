"""Ship-time tool: turn the FILLED tree into the CARVED starter.
Run: python scripts/carve.py [HOLE …]   (no args = the SHIPPED holes)
       python scripts/carve.py --all    (every registry hole - authoring only)
Inverse of scripts/rescue.py; both read checks/holes.py.

v6 watch-first: students only hand-edit three spots; everything else ships
filled and is taught as read-along code."""
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from checks.holes import HOLES  # noqa: E402

# the three spots the student fills: draw the base graph, then wire in a
# new research feed per act - the graph literally grows
SHIP_HOLES = ["EDGES", "GRAPH_EDGE", "MEMORY_EDGE"]


def main():
    args = sys.argv[1:]
    names = (list(HOLES) if "--all" in args else
             [a for a in args if a in HOLES] or SHIP_HOLES)
    for name in names:
        rel, anchor, snippet = HOLES[name]
        p = ROOT / rel
        src = p.read_text()
        if anchor in src:
            print(f"  - {name}: already carved")
            continue
        if snippet not in src:
            print(f"  ✗ {name}: snippet not found in {rel} — tree drifted from registry")
            sys.exit(1)
        p.write_text(src.replace(snippet, anchor, 1))
        print(f"  ✓ {name}: carved out of {rel}")


if __name__ == "__main__":
    main()
