"""Wipe local run state for a fresh start (never touches BigQuery / Memory Bank).
Run: python scripts/reset.py [--all] [--archive]
     --all      also wipes the wall + the thumbnails its rows point at
     --archive  copies what it removes into runs/archive/<stamp>/ first

The Now page's Restart control imports clear() from here, so the button and
the CLI cannot drift into two different opinions about what a lap owns.
"""
import json
import pathlib
import shutil
import sys
import time

ROOT = pathlib.Path(__file__).resolve().parent.parent
RUNS = ROOT / "runs"
ARCHIVE = RUNS / "archive"
THUMBS = ROOT / "app" / "static" / "thumbs"

# What ONE lap owns on disk. Everything here is written by a lap, read back as
# that lap's truth, and is a lie the moment the next lap starts:
#   state.json      the lap itself
#   sessions.db     the lap's ADK session, incl. its open long-running calls
#   broker.json     the lap's Veo jobs + the degraded flag farm_note() reads
#   ui_busy.json    which worker is running (a pid, and pids get recycled)
#   ui_last.json    how the last worker exited - failed_card() renders it
#   ui_control.json the receipt End/Restart leaves for the page
#   *_run.log       the worker output failed_card() and stages.log_tail() show
LAP_FILES = ("state.json", "sessions.db", "broker.json", "ui_busy.json",
             "ui_last.json", "ui_control.json")
# NOT here, on purpose: runs/wall.db is PUBLISHED history (the Channel page and
# agent.learn read it, and its rows point at app/static/{thumbs,renders}), and
# runs/archive/ is where the archived copies go. Only --all touches the wall.
WALL_FILES = ("wall.db",)


def lap_paths() -> list[pathlib.Path]:
    """Every artifact of the current lap that exists right now."""
    return [p for p in ([RUNS / f for f in LAP_FILES] + sorted(RUNS.glob("*_run.log")))
            if p.exists()]


def wall_paths() -> list[pathlib.Path]:
    """Published history: the wall, and the thumbnails its rows point at."""
    return [p for p in [RUNS / f for f in WALL_FILES] if p.exists()] + \
           sorted(THUMBS.glob("*.png"))


def clear(wall: bool = False, archive: bool = False) -> dict:
    """Remove the lap's artifacts. Returns {'cleared': [...], 'archive': str|''}.

    Paths come back repo-relative, because that is how the console and this
    script both talk about them. Never raises on a file that will not budge -
    it reports it instead, so a caller can say so on the page.
    """
    targets = lap_paths() + (wall_paths() if wall else [])
    into = ""
    if archive and targets:
        stamp = time.strftime("%Y%m%d-%H%M%S")
        dest = ARCHIVE / stamp
        dest.mkdir(parents=True, exist_ok=True)
        for t in targets:
            try:
                shutil.copy2(t, dest / t.name)
            except OSError:
                pass                       # a copy we could not take is not a
        into = str(dest.relative_to(ROOT))  # reason to leave the lap running
    cleared, stuck = [], []
    for t in targets:
        try:
            t.unlink()
            cleared.append(str(t.relative_to(ROOT)))
        except OSError as e:
            stuck.append(f"{t.relative_to(ROOT)} ({e.strerror})")
    return {"cleared": cleared, "archive": into, "stuck": stuck}


def quarantine(*paths: pathlib.Path) -> list[str]:
    """A killed worker can be halfway through a write. Any of these JSON files
    that no longer parses is moved out of runs/ - a truncated state.json is
    read by every page, and one bad byte would 500 the console forever.

    Returns the repo-relative paths that had to be moved.
    """
    moved = []
    for p in paths:
        if not p.exists():
            continue
        try:
            json.loads(p.read_text())
            continue                       # parses - it is somebody's truth
        except (OSError, ValueError):
            pass
        dest = ARCHIVE / time.strftime("%Y%m%d-%H%M%S")
        try:
            dest.mkdir(parents=True, exist_ok=True)
            shutil.move(str(p), str(dest / f"broken-{p.name}"))
            moved.append(str(p.relative_to(ROOT)))
        except OSError:
            try:
                p.unlink()                 # unreadable AND unmovable: it still
                moved.append(str(p.relative_to(ROOT)))   # cannot stay
            except OSError:
                pass
    return moved


if __name__ == "__main__":
    out = clear(wall="--all" in sys.argv, archive="--archive" in sys.argv)
    for p in out["cleared"]:
        print(f"removed {p}")
    for p in out["stuck"]:
        print(f"could not remove {p}")
    if out["archive"]:
        print(f"archived a copy of each into {out['archive']}")
    print("reset done" + (" (restart the server if you wiped the wall)"
                          if "--all" in sys.argv else ""))
