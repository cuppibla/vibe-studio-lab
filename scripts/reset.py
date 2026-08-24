"""Wipe local run state for a fresh start (never touches BigQuery / Memory Bank).
Run: python scripts/reset.py [--all]   (--all also wipes the wall + thumbnails)"""
import pathlib
import sys

root = pathlib.Path(__file__).resolve().parent.parent
targets = [root / "runs" / f for f in ("state.json", "sessions.db", "broker.json",
                                       "ui_busy.json")]
if "--all" in sys.argv:
    targets += [root / "runs" / "wall.db"]
    targets += sorted((root / "app" / "static" / "thumbs").glob("*.png"))
for t in targets:
    if t.exists():
        t.unlink()
        print(f"removed {t.relative_to(root)}")
print("reset done" + (" (restart the server if you wiped the wall)" if "--all" in sys.argv else ""))
