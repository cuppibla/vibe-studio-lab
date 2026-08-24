"""Author-side proof: for every hole-bearing file,
  carve(filled) + all snippets == solutions/<file>, byte for byte,
and every anchor/snippet is actually present where the registry says.
Run: python -m checks.verify_holes   (works from the filled OR carved tree)"""
import pathlib
import sys
from collections import defaultdict

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from checks.holes import HOLES  # noqa: E402

fails = []
by_file = defaultdict(list)
for name, (rel, anchor, snippet) in HOLES.items():
    by_file[rel].append((name, anchor, snippet))

for rel, items in sorted(by_file.items()):
    live = (ROOT / rel).read_text()
    sol = (ROOT / "solutions" / rel).read_text()
    # normalize the live file to CARVED form, then fill every hole from snippets
    carved = live
    for name, anchor, snippet in items:
        if snippet in carved:
            carved = carved.replace(snippet, anchor, 1)
        if anchor not in carved:
            print(f"  ✗ {name}: neither snippet nor anchor found in {rel}")
            fails.append(name)
    filled = carved
    names = []
    for name, anchor, snippet in items:
        if anchor not in filled:
            continue
        filled = filled.replace(anchor, snippet, 1)
        names.append(name)
    if filled == sol:
        print(f"  ✓ {rel}: {' + '.join(names)} reproduce the solution exactly")
    else:
        print(f"  ✗ {rel}: carve→fill does NOT reproduce solutions/{rel}")
        import difflib
        for line in list(difflib.unified_diff(sol.splitlines(), filled.splitlines(),
                                              lineterm=""))[:10]:
            print("     ", line)
        fails.append(rel)

print()
if fails:
    print(f"HOLES VERIFY: {len(fails)} FAILURE(S): {fails}"); sys.exit(1)
print(f"HOLES VERIFY: all {len(HOLES)} holes round-trip byte-for-byte")
