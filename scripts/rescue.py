"""Stuck? Fill ONE hole with its solution and move on.
Run: python scripts/rescue.py <hole|section>
       python scripts/rescue.py            (no args = fill every hole)
Holes: RESUME · EDGES · TASK_WORD · CREATIVE_GATE · JOIN_CONDITION · PREFS ·
EDGE_TABLE · GENERATE · RECALL   Sections: s1 · s2 · s3 · s4 · s5
A rescued file is byte-identical to a hand-pasted one (checks/verify_holes.py
guards that)."""
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from checks.holes import HOLES, SECTIONS  # noqa: E402


def main():
    arg = (sys.argv[1] if len(sys.argv) > 1 else "").upper()
    names = (list(HOLES) if arg in ("", "ALL") else
             SECTIONS.get(arg.lower()) or ([arg] if arg in HOLES else None))
    if not names:
        print(f"usage: rescue.py <hole|section>   holes: {' · '.join(HOLES)}   "
              f"sections: {' · '.join(SECTIONS)}")
        sys.exit(2)
    for name in names:
        rel, anchor, snippet = HOLES[name]
        p = ROOT / rel
        src = p.read_text()
        if anchor not in src:
            print(f"  - {name}: no open hole in {rel} (already filled?) — skipping")
            continue
        p.write_text(src.replace(anchor, snippet, 1))
        print(f"  ✓ {name}: solution pasted into {rel}")


if __name__ == "__main__":
    main()
