"""Vibe Studio - ONE server, two faces:
  · the Wall API (the platform contract the agent publishes to)
  · the console (Now / Channel / State) - a VIEW over the same durable state,
    whose every button just runs the same CLI the student runs. The button IS
    the delivered result.
"""
from __future__ import annotations

import html
import json
import os
import signal
import sqlite3
import subprocess
import sys
import time
import uuid
from pathlib import Path

from fastapi import FastAPI, Form, Header, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from agent import config, drive, state  # noqa: E402
from app import stages  # noqa: E402  (pure reader over runs/*.json - no graph import)
from scripts import reset  # noqa: E402  (ONE list of what a lap owns on disk)
from world import broker, simulator  # noqa: E402
# NOTE: `agent.lap` (→ agent.graph) is imported lazily inside now_body — in the
# carved starter the EDGES hole raises on import, and Studio must stay up to
# tell you which hole to fill instead of dying with the graph.

app = FastAPI(title="Vibe Studio")
app.mount("/static", StaticFiles(directory=Path(__file__).parent / "static"), name="static")

from world.platform import SEED_TRENDS as TRENDS  # noqa: E402  (one list, two readers)

# ══════════════════════════ the Wall API ══════════════════════════


def db() -> sqlite3.Connection:
    conn = sqlite3.connect(config.WALL_DB)
    conn.row_factory = sqlite3.Row
    return conn


def init() -> None:
    with db() as c:
        c.executescript("""
            CREATE TABLE IF NOT EXISTS creators(
              id TEXT PRIMARY KEY, handle TEXT UNIQUE, token TEXT, joined_at REAL);
            CREATE TABLE IF NOT EXISTS videos(
              id TEXT PRIMARY KEY, creator_id TEXT, title TEXT, description TEXT,
              duration_ms INTEGER, lap INTEGER, video_ref TEXT, thumb_ref TEXT,
              lineage TEXT, published_at REAL);
            CREATE TABLE IF NOT EXISTS views(
              id INTEGER PRIMARY KEY AUTOINCREMENT, video_id TEXT, viewer_id TEXT,
              watched_ms INTEGER, drop_ms INTEGER, completed INTEGER,
              is_synthetic INTEGER, at REAL);
            CREATE TABLE IF NOT EXISTS publish_keys(
              key TEXT PRIMARY KEY, response TEXT);
            """)


init()


class Join(BaseModel):
    handle: str


class Publish(BaseModel):
    creator_id: str
    token: str
    title: str
    description: str = ""
    duration_ms: int
    lap: int = 1
    video_ref: str
    thumb_ref: str = ""
    lineage: dict


@app.post("/api/join")
def join(body: Join):
    with db() as c:
        row = c.execute("SELECT * FROM creators WHERE handle=?", (body.handle,)).fetchone()
        if row:
            return {"creator_id": row["id"], "token": row["token"]}
        cid, token = f"c_{uuid.uuid4().hex[:8]}", uuid.uuid4().hex
        c.execute("INSERT INTO creators VALUES (?,?,?,?)",
                  (cid, body.handle, token, time.time()))
    return {"creator_id": cid, "token": token}


@app.get("/api/trends")
def trends():
    return {"trends": TRENDS}


def _auth(c, creator_id: str, token: str) -> None:
    row = c.execute("SELECT token FROM creators WHERE id=?", (creator_id,)).fetchone()
    if not row or row["token"] != token:
        raise HTTPException(401, "bad creator token")


@app.post("/api/publish")
def publish(body: Publish, idempotency_key: str = Header(alias="Idempotency-Key")):
    with db() as c:
        _auth(c, body.creator_id, body.token)
        seen = c.execute("SELECT response FROM publish_keys WHERE key=?",
                         (idempotency_key,)).fetchone()
        if seen:  # replay returns the ORIGINAL response - retries cannot double-publish
            return json.loads(seen["response"])
        vid = f"v_{uuid.uuid4().hex[:8]}"
        c.execute("INSERT INTO videos VALUES (?,?,?,?,?,?,?,?,?,?)",
                  (vid, body.creator_id, body.title, body.description,
                   body.duration_ms, body.lap, body.video_ref, body.thumb_ref,
                   json.dumps(body.lineage), time.time()))
        for r in simulator.simulate_audience(vid, body.duration_ms, body.lineage):
            c.execute(
                "INSERT INTO views(video_id,viewer_id,watched_ms,drop_ms,completed,"
                "is_synthetic,at) VALUES (?,?,?,?,?,?,?)",
                (vid, r["viewer_id"], r["watched_ms"], r["drop_ms"],
                 int(r["completed"]), 1, time.time()))
        resp = {"video_id": vid, "url": f"/watch/{vid}"}
        c.execute("INSERT INTO publish_keys VALUES (?,?)", (idempotency_key, json.dumps(resp)))
    return resp


@app.get("/api/outcomes")
def outcomes(creator_id: str):
    with db() as c:
        vids = c.execute("SELECT * FROM videos WHERE creator_id=?", (creator_id,)).fetchall()
        out = []
        for v in vids:
            views = c.execute("SELECT * FROM views WHERE video_id=?", (v["id"],)).fetchall()
            n = len(views) or 1
            avg_pct = sum(r["watched_ms"] for r in views) / (n * v["duration_ms"]) * 100
            drops = sorted(r["drop_ms"] for r in views if r["drop_ms"] is not None)
            out.append({
                "video_id": v["id"], "title": v["title"], "lap": v["lap"],
                "duration_ms": v["duration_ms"], "views": n,
                "avg_watch_pct": round(avg_pct, 1),
                "median_drop_ms": drops[len(drops) // 2] if drops else None,
                "dropped_pct": round(len(drops) / n * 100, 1),
                "view_rows": [dict(r) for r in views],
            })
    return {"videos": out}


# ══════════════════════════ the console ══════════════════════════

BUSY = config.RUNS / "ui_busy.json"
LAST = config.RUNS / "ui_last.json"   # how the last button ended, for the page
CONTROL = config.RUNS / "ui_control.json"  # what End / Restart just did, for the page
PY = str(config.ROOT / ".venv" / "bin" / "python")


def _worker_log(verb: str):
    """Every button's child writes here, same as spawn_logged() - a worker that
    dies must leave its reason on disk, or the page pends on it forever."""
    return (config.RUNS / f"{verb}_run.log").open("w")


def _started(verb: str, pid: int) -> None:
    """One record per press: what is running, and no stale outcome from before."""
    BUSY.write_text(json.dumps({"verb": verb, "pid": pid, "at": time.time()}))
    LAST.unlink(missing_ok=True)
    CONTROL.unlink(missing_ok=True)       # ...including the last End / Restart


def _finished(verb: str, code: int) -> None:
    """...and how it ended. This used to be dropped on the floor."""
    LAST.write_text(json.dumps({"verb": verb, "code": code, "at": time.time()}))
    BUSY.unlink(missing_ok=True)


def spawn(verb: str, *args) -> None:
    """Every button runs the SAME command the student runs. The button is the CLI.
    One at a time: a double-click must not start two runs."""
    if busy():
        return
    env = {**os.environ, "PYTHONUNBUFFERED": "1"}
    with _worker_log(verb) as log:            # the child keeps its own handle
        p = subprocess.Popen([PY, "-m", f"agent.{verb}", *args], cwd=config.ROOT,
                             env=env, stdout=log, stderr=subprocess.STDOUT)
    _started(verb, p.pid)


def spawn_force(verb: str, *args) -> None:
    """Like spawn(), but for the buttons that must never be swallowed by a
    still-running worker (Approve/Regenerate) - it skips the busy() check and
    starts regardless."""
    env = {**os.environ, "PYTHONUNBUFFERED": "1"}
    with _worker_log(verb) as log:
        p = subprocess.Popen([PY, "-m", f"agent.{verb}", *args], cwd=config.ROOT,
                             env=env, stdout=log, stderr=subprocess.STDOUT)
    _started(verb, p.pid)


def spawn_sh(verb: str, script: str) -> None:
    """Same contract as spawn(), for the one step that IS a shell script:
    the World button runs `bash scripts/graph.sh`, unbuffered, into a log the
    page tails while it runs."""
    if busy():
        return
    env = {**os.environ, "PYTHONUNBUFFERED": "1",
           "PATH": f"{config.ROOT / '.venv' / 'bin'}:{os.environ.get('PATH', '')}"}
    with _worker_log(verb) as log:
        proc = subprocess.Popen(["bash", script], cwd=config.ROOT, env=env,
                                stdout=log, stderr=subprocess.STDOUT)
    _started(verb, proc.pid)


def spawn_logged(verb: str) -> None:
    """spawn(), but the command's output goes to runs/<verb>_run.log so the
    page can show it - for the one-time CONNECT steps (the bank)."""
    if busy():
        return
    env = {**os.environ, "PYTHONUNBUFFERED": "1"}
    with _worker_log(verb) as log:
        p = subprocess.Popen([PY, "-m", f"agent.{verb}"], cwd=config.ROOT, env=env,
                             stdout=log, stderr=subprocess.STDOUT)
    _started(verb, p.pid)


def busy() -> str | None:
    """Which button is still running, if any. Reaps first: a finished child
    stays in the process table as a zombie until someone waits on it, and a
    zombie answers signal 0 - it would look busy forever."""
    if not BUSY.exists():
        return None
    b = json.loads(BUSY.read_text())
    try:
        pid, status = os.waitpid(b["pid"], os.WNOHANG)
        if pid == b["pid"]:                  # it just finished; reaped now
            _finished(b["verb"], os.waitstatus_to_exitcode(status))
            return None
    except ChildProcessError:
        pass                                 # not ours / already reaped
    try:
        os.kill(b["pid"], 0)
        return b["verb"]
    except OSError:
        return None


# ── stopping what busy() is watching ──────────────────────────────────────
# busy() reaps and reports; these three stop. Same rules apply: only the pid
# on record is ever signalled, and a finished child is waited on so it cannot
# sit in the process table as a zombie answering signal 0 forever.

GRACE_S = 2.0        # SIGTERM, this long to die quietly, then SIGKILL


def _reap(pid: int) -> int | None:
    """Wait on our own child without blocking: its exit code once it is really
    gone, or None if it is still running / was never ours to reap."""
    try:
        got, status = os.waitpid(pid, os.WNOHANG)
    except (ChildProcessError, OSError):
        return None                       # not our child - its parent reaps it
    return os.waitstatus_to_exitcode(status) if got == pid else None


def _alive(pid: int) -> bool:
    """signal 0. A zombie answers it, so _reap() always runs first."""
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True                       # someone else's process: alive, not ours
    except OSError:
        return False
    return True


def _gone(pid: int, secs: float) -> tuple[bool, int | None]:
    """Poll until the pid is gone or the grace runs out, reaping as we go."""
    end = time.monotonic() + secs
    while True:
        code = _reap(pid)
        if code is not None:
            return True, code
        if not _alive(pid):
            return True, None
        if time.monotonic() >= end:
            return False, None
        time.sleep(0.05)


def stop_worker() -> dict:
    """Stop whatever runs/ui_busy.json says is running and clear the slot.

    Returns {verb, pid, how, code} for the page. It never raises: a control
    whose whole job is getting a stuck learner unstuck must not 500 on a
    missing file, a truncated one, a pid that died a second ago, a pid that
    was recycled into someone else's process, or a worker started by a server
    that has since been restarted (an orphan we can signal but never reap).
    """
    if not BUSY.exists():
        return {"how": "nothing was running"}
    try:
        b = json.loads(BUSY.read_text())
        verb, pid = str(b.get("verb") or "?"), int(b.get("pid") or 0)
    except (OSError, ValueError, TypeError):
        BUSY.unlink(missing_ok=True)
        return {"how": "cleared a busy file that no longer parsed"}
    if pid <= 0:
        BUSY.unlink(missing_ok=True)
        return {"verb": verb, "how": "had no pid on record - cleared the slot"}

    code = _reap(pid)                     # finished on its own between clicks?
    if code is not None:
        _finished(verb, code)             # the same record busy() would write
        return {"verb": verb, "pid": pid, "code": code,
                "how": f"had already finished on its own (exit {code})"}
    if not _alive(pid):
        BUSY.unlink(missing_ok=True)
        return {"verb": verb, "pid": pid, "how": "was already gone"}

    how, done, code = "was already gone", False, None
    for sig, name in ((signal.SIGTERM, "SIGTERM"), (signal.SIGKILL, "SIGKILL")):
        try:
            os.kill(pid, sig)             # the recorded pid, and nothing else
        except ProcessLookupError:
            done, code = _gone(pid, 0.5)  # it beat us to it - still reap it
            done = True
            break
        except (PermissionError, OSError):
            BUSY.unlink(missing_ok=True)
            return {"verb": verb, "pid": pid,
                    "how": "is not ours to signal - the pid belongs to another "
                           "process now, so the stale slot was cleared instead"}
        how = f"stopped with {name}"
        done, code = _gone(pid, GRACE_S if sig == signal.SIGTERM else GRACE_S)
        if done:
            break
    if not done:
        how += " - it has not exited yet"
    BUSY.unlink(missing_ok=True)
    out = {"verb": verb, "pid": pid, "how": how}
    if code is not None:
        out["code"] = code
    return out


def _receipt(action: str, stopped: dict, cleared: list[str], kept: list[str],
             archive: str = "", moved: list[str] | None = None) -> None:
    """One record per control press, read back by control_card(). Cleared by
    _started(), so the page can never show a receipt from two laps ago."""
    CONTROL.write_text(json.dumps({
        "action": action, "at": time.time(), "stopped": stopped,
        "cleared": cleared, "kept": kept, "archive": archive,
        "moved": moved or [],
    }))


def control_card() -> str:
    """What End / Restart just did, in the same grammar as failed_card(): what
    was stopped, what was cleared, and what deliberately survived."""
    if not CONTROL.exists():
        return ""
    try:
        r = json.loads(CONTROL.read_text())
    except (OSError, ValueError):
        return ""
    s = r.get("stopped") or {}
    verb, pid = s.get("verb"), s.get("pid")
    who = f"python -m agent.{verb}" + (f" (pid {pid})" if pid else "") if verb else ""
    stopped = f"{who} {s.get('how', '')}".strip() if who else str(s.get("how", ""))
    head = ("You ended the lap. Nothing is running."
            if r.get("action") == "end" else
            "You restarted. This is a fresh lap.")
    rows = [f'<div class="h0s">{html.escape(stopped)}</div>']
    for label, items in (("cleared", r.get("cleared") or []),
                         ("kept", r.get("kept") or []),
                         ("moved aside, it no longer parsed", r.get("moved") or [])):
        if items:
            rows.append(f'<div class="h0s" style="margin-top:7px">{html.escape(label)}: '
                        f'<span class="mono">{html.escape(", ".join(str(i) for i in items))}'
                        f'</span></div>')
    if r.get("archive"):
        rows.append('<div class="h0s" style="margin-top:7px">a copy of everything cleared '
                    f'is in <span class="mono">{html.escape(str(r["archive"]))}</span></div>')
    return f"""
<div class="card" style="border-left:4px solid #8A8072;margin-bottom:18px">
<div class="h0" style="font-size:19px">{head}</div>
{"".join(rows)}</div>"""


def farm_note() -> str:
    """Veo failed over? Say so on every card of the lap. A learner must never
    finish this chapter believing a prebaked stand-in came out of Veo."""
    dg = broker.degraded()
    if not dg:
        return ""
    return f"""
<div class="card" style="border-left:4px solid #E8945A;margin-bottom:18px">
<div class="h0" style="font-size:19px">Veo is unreachable — this lap fell back to the prebaked clock.</div>
<div class="h0s">retried once, then degraded so the lab keeps moving · the clips below are
<b>stand-ins, not Veo output</b></div>
<div class="h0s mono" style="margin-top:9px">{html.escape(dg.get("reason", ""))}</div></div>"""


def failed_card() -> str:
    """The other half of the log: a worker that exited non-zero used to vanish
    here and leave the page pending forever. Say it died, and show the tail."""
    if not LAST.exists():
        return ""
    try:
        f = json.loads(LAST.read_text())
    except (OSError, ValueError):
        return ""
    if not f.get("code"):
        return ""                            # exited 0 - nothing to report
    # the tail reader lives in app/stages.py - the stage list shows the last
    # line of it as that stage's reason, and one implementation cannot disagree
    # with itself about what the log said
    tail = "<br>".join(html.escape(l) for l in stages.log_tail(f["verb"], 6))
    return f"""
<div class="card" style="border-left:4px solid #C97B6B;margin-bottom:18px">
<div class="h0" style="font-size:19px">python -m agent.{f["verb"]} exited {f["code"]}.</div>
<div class="h0s">nothing is running — the lap is exactly where the worker left it ·
full output in <span class="mono">runs/{f["verb"]}_run.log</span></div>
<div class="h0s mono" style="margin-top:11px;line-height:1.65">{tail}</div></div>"""


CSS = """
:root{--bg:#FAF6EF;--card:#FFF;--ink:#2A2520;--sub:#8A8072;--line:#EAE2D4;
--amber:#E9A23B;--blue:#82AEE3;--teal:#5BBFA9;--violet:#A98BD9;--orange:#E8945A;
--sh:0 12px 34px rgba(70,50,25,.09)}
*{box-sizing:border-box;margin:0;padding:0}
body{background:var(--bg);color:var(--ink);font-family:-apple-system,'SF Pro Text','Google Sans',sans-serif}
.mono{font-family:'SF Mono',Menlo,monospace}
.top{display:flex;align-items:center;gap:10px;padding:16px 26px;background:var(--card);border-bottom:1px solid var(--line)}
.top img.logo{width:26px;height:26px;border-radius:8px;object-fit:cover}
.brand{font-size:15px;font-weight:700}
.tabs{display:flex;gap:6px;margin-left:26px}
.tab{font-size:13.5px;color:var(--sub);padding:7px 14px;border-radius:20px;text-decoration:none}
.tab.on{color:var(--ink);background:var(--bg);font-weight:600}
.me{margin-left:auto;width:30px;height:30px;border-radius:50%;overflow:hidden}
.me img{width:100%;height:100%;object-fit:cover}
.wrap{max-width:880px;margin:34px auto;padding:0 24px}
.card{background:var(--card);border-radius:24px;box-shadow:var(--sh);padding:32px 38px;border:1px solid rgba(0,0,0,.03)}
.h0{font-size:25px;font-weight:700}.h0s{color:var(--sub);font-size:13.5px;margin-top:6px}
.ql{font-size:11px;letter-spacing:.16em;color:var(--sub);font-weight:600;margin:22px 0 9px}
.chips{display:flex;gap:9px;flex-wrap:wrap}
.drow{display:flex;gap:12px;align-items:flex-start;padding:11px 12px;border:1.6px solid var(--line);border-radius:12px;margin-top:9px;cursor:pointer}
.drow input[type=radio]{margin-top:5px;accent-color:var(--amber)}
.drow b{font-size:15.5px}
.drow input[type=text]{margin-top:6px;width:100%}
.chip{font-size:14px;padding:8px 15px;border-radius:22px;border:1.5px solid var(--line);background:#fff;color:var(--ink);cursor:pointer}
.chip.on{border-color:var(--amber);background:rgba(233,162,59,.09);font-weight:600}
input[type=text]{border:1.5px solid var(--line);border-radius:13px;padding:11px 15px;font-size:14.5px;width:100%;max-width:430px;background:#fff}
select{border:1.5px solid var(--line);border-radius:13px;padding:10px 13px;font-size:14px;background:#fff}
.foot{display:flex;align-items:center;margin-top:26px;gap:14px}
.go{margin-left:auto;background:var(--ink);color:#fff;font-size:14.5px;font-weight:600;padding:12px 28px;border-radius:13px;border:none;cursor:pointer}
.ghost{border:1.5px solid var(--line);background:#fff;color:var(--sub);font-size:13px;padding:11px 16px;border-radius:12px;cursor:pointer}
.danger{border:1.5px solid #C97B6B;background:#fff;color:#A65B4B;font-size:14.5px;font-weight:600;padding:12px 24px;border-radius:13px;cursor:pointer}
.hero{border-radius:24px;overflow:hidden;box-shadow:var(--sh)}.hero img{width:100%;display:block}
.busy{display:inline-flex;align-items:center;gap:8px;font-size:12.5px;color:var(--sub);margin-bottom:14px}
.dot{width:8px;height:8px;border-radius:50%;background:var(--amber);animation:p 1.2s infinite}
@keyframes p{50%{opacity:.3}}
.prop{display:flex;gap:16px;align-items:flex-start}
.prop img{width:60px;height:60px;border-radius:16px;object-fit:cover}
.prop .t{font-size:17px;font-weight:600;line-height:1.45;white-space:pre-wrap}
.grid{display:flex;gap:18px;flex-wrap:wrap}
.v{width:calc(50% - 9px);border:1px solid var(--line);border-radius:18px;overflow:hidden;background:#fff}
.v img,.v video{width:100%;height:180px;object-fit:cover;display:block;background:#000}
.play{position:relative;height:180px;background:#000;cursor:pointer}
.play img,.play video{position:absolute;inset:0;width:100%;height:100%;object-fit:cover}
.play video{display:none}
.play .pb{position:absolute;left:50%;top:50%;transform:translate(-50%,-50%);width:52px;height:52px;border-radius:50%;background:rgba(43,35,32,.72);color:#fff;font-size:18px;display:flex;align-items:center;justify-content:center;padding-left:4px}
.play.on img,.play.on .pb{display:none}.play.on video{display:block}
.flow{margin:0 0 18px;padding:20px 16px 14px;background:#fff;border:1px solid var(--line);border-radius:18px;overflow-x:auto}
.fs{display:flex;flex-direction:column;align-items:center;min-width:96px;flex:1}
.fd{width:15px;height:15px;border-radius:50%;border:2px solid #D9CFC0;background:#fff}
.fs.done .fd{background:#C96442;border-color:#C96442}
.fs.now .fd{background:#E9B44C;border-color:#E9B44C;box-shadow:0 0 0 5px rgba(233,180,76,.22)}
.fs.you .fd{background:#fff;border-color:#E9B44C;box-shadow:0 0 0 5px rgba(233,180,76,.22)}
.fl{font-size:11.5px;margin-top:8px;color:var(--sub);text-align:center;line-height:1.3}
.fs.done .fl,.fs.now .fl,.fs.you .fl{color:var(--ink)}
.fs.you .fl b{color:#B4802A}
.fbar{height:2px;background:#EDE5D8;flex:1;margin-top:6px;min-width:14px}
.fbar.on{background:#C96442}
.vi{padding:13px 16px;display:flex;align-items:baseline;gap:10px}
.vt{font-size:14px;font-weight:600;flex:1;line-height:1.35}
.vp{font-size:21px;font-weight:300}.vp small{font-size:11px;color:var(--sub)}
.made{margin-top:16px;display:flex;gap:8px;align-items:center;flex-wrap:wrap}
.k{font-size:11px;letter-spacing:.16em;color:var(--sub);font-weight:600;margin-right:4px}
.mchip{font-size:12.5px;padding:5px 12px;border-radius:16px;border:1.5px solid var(--line)}
.mm{border-color:rgba(232,148,90,.6);color:#B45D22}.mg{border-color:rgba(169,139,217,.6);color:#6D4FA8}
.row{display:flex;align-items:center;gap:18px;padding:15px 4px;border-bottom:1px solid var(--line)}
.row:last-of-type{border-bottom:none}
.row img{width:42px;height:54px;object-fit:cover;border-radius:10px}
.rn{width:160px}.rn b{font-size:15px;display:block}.rn span{font-size:11.5px;color:var(--sub)}
.rv{flex:1;font-size:13px;color:#5C5346;line-height:1.7}
.rv .hot{color:#B47A1E;font-weight:600}
.life{font-size:11.5px;color:var(--sub);width:150px;text-align:right}
.kill{margin-top:16px;text-align:center;font-size:13.5px;color:var(--sub)}
.kill b{color:var(--ink)}
.thumbprev{border-radius:16px;max-width:420px;display:block;margin:6px 0 2px}
.note{font-size:13px;color:#5C5346;padding:2px 0}
.x{color:#C97B6B;font-size:12px;text-decoration:none;margin-left:10px}
.stlist{margin-top:16px;border-top:1px solid var(--line)}
.stg{display:flex;gap:12px;align-items:flex-start;padding:10px 2px;border-bottom:1px solid var(--line)}
.stg:last-child{border-bottom:none}
.stm{width:18px;flex:none;text-align:center;font-size:13px;line-height:1.5;color:#C4B9A8}
.stl{font-size:14.5px;font-weight:600;color:var(--sub)}
.sts{font-size:12.5px;color:var(--sub);margin-top:2px}
.stn{font-size:12px;color:#5C5346;margin-top:5px;line-height:1.6;word-break:break-word}
.stw{font-size:10px;letter-spacing:.14em;font-weight:700;margin-left:9px;vertical-align:1px}
.stg.pass .stm{color:#C96442}.stg.pass .stl{color:var(--ink)}.stg.pass .stw{color:#C96442}
.stg.now .stm{color:#E9B44C}.stg.now .stl{color:var(--ink)}.stg.now .stw{color:#B4802A}
.stg.now .stm{animation:p 1.2s infinite}
.stg.fail .stm,.stg.fail .stw{color:#C97B6B}.stg.fail .stl{color:var(--ink)}
.stg.fail .stn{color:#A65B4B}
.stg.retry .stm,.stg.retry .stw{color:#E8945A}.stg.retry .stl{color:var(--ink)}
.stg.degraded .stm,.stg.degraded .stw{color:#E8945A}.stg.degraded .stl{color:var(--ink)}
.stg.blocked .stm,.stg.blocked .stw{color:#C97B6B}.stg.blocked .stl{color:var(--ink)}
.stg.skip .stm,.stg.skip .stw{color:#B3A897}
.stg.stall .stm,.stg.stall .stw{color:#8A8072}.stg.stall .stl{color:var(--ink)}
.stg.wait .stm,.stg.wait .stw{color:#E9B44C}.stg.wait .stl{color:var(--ink)}
.stk{color:#B4802A}
"""


MASCOT = "/static/art/robot-avatar.png"   # the studio's mascot walks the map


def suggest_topic() -> str:
    """PERSISTENT STATE, visible: user:prefs remembers your last direction
    across every session, so the next visit can open with a suggestion."""
    try:
        prefs = drive.run(drive.ensure_user_state("_ui_probe")).get("user:prefs") or {}
        return prefs.get("last_direction", "")
    except Exception:
        return ""



def page(tab: str, body: str, refresh: bool = True) -> str:
    tabs = "".join(
        f'<a class="tab{" on" if tab == t.lower() else ""}" href="/{"" if t == "Now" else t.lower()}">{t}</a>'
        for t in ("Now", "Channel", "State", "World"))
    meta = '<meta http-equiv="refresh" content="4">' if refresh else ""
    return f"""<!doctype html><html><head><meta charset="utf-8">{meta}
<title>Vibe Studio</title><style>{CSS}</style></head><body>
<div class="top"><img class="logo" src="/static/art/gem-3.png"><span class="brand">Vibe Studio</span>
<div class="tabs">{tabs}</div>
</div>
<div class="wrap">{body}</div></body></html>"""


def now_body() -> str:
    try:
        from agent import lap  # noqa: F401 — may raise while holes are open
    except NotImplementedError as e:
        return f"""<div class="card"><div class="h0">A hole is open.</div>
<div class="h0s mono" style="margin-top:10px">{str(e)}</div>
<div class="h0s" style="margin-top:14px">fill it in your editor, then come back — this page refreshes itself</div></div>"""
    st = state.load()
    b = busy()
    busy_html = (f'<div class="busy"><span class="dot"></span>{b} is running — this page refreshes itself</div>'
                 if b else failed_card())
    busy_html += farm_note()
    busy_html += control_card()          # what End / Restart just did, if anything
    if st.get("run_id"):
        # WHERE the lap is, stage by stage - derived from runs/state.json,
        # runs/broker.json and the worker logs, so it survives a restart. The
        # detail stays in the two cards above: this list says which stage they
        # belong to.
        phase = lap.where().get("phase", "")
        busy_html += stages.render(st, phase, b)
        # the live map of the workflow (nodes+edges dumped from the real
        # Workflow object), above every card of a running lap
        from app import flowmap
        busy_html += flowmap.render(st, phase, MASCOT)
    else:
        busy_html += stages.render(st, "idle", b)

    if not st.get("run_id"):
        chip = ""
        sug = suggest_topic()
        if sug:
            chip = (f'<div class="h0s" style="margin-bottom:8px">the channel remembers '
                    f'your taste — <span class="mchip">something like: {sug}</span></div>')
        return busy_html + f"""
<div class="hero"><img src="/static/art/hero-studio.png"></div>
<div class="card" style="margin-top:22px">
<div class="h0">Everything is asleep. The state is safe.</div>
<div class="h0s">Drop an idea — or drop nothing, and the channel finds its own.</div>
{chip}<form method="post" action="/ui/run"><div class="foot">
<input type="text" name="hint" placeholder='an idea — or leave it empty'>
<button class="go">Start a lap ▸</button></div></form>
<div class="h0s" style="margin-top:14px">you get three touches: this idea · picking a direction · approving the thumbnail</div></div>"""

    if st.get("published"):
        v = st["published"]
        room = st.get("room") or {}
        if room.get("url"):
            room_row = (f'<div class="h0s">and the room can see you — '
                        f'<a href="{room["url"]}" target="_blank">watch it with everyone else ↗</a></div>')
        elif room.get("skipped") and room["skipped"] != "no room configured":
            room_row = (f'<div class="h0s" style="color:var(--sub)">room: skipped '
                        f'({room["skipped"]})</div>')
        else:
            room_row = ""
        # the Learn button exists only once there is a bank to write into -
        # same rule as the map: nothing is drawn until it is real
        from agent import memory as _memory
        learn = ""
        if _memory.engine_name():
            learn = """
<form method="post" action="/ui/learn"><div style="text-align:right">
<button class="go">Learn from the audience ▸</button><br>
<span style="font-size:12.5px;color:var(--sub)">python -m agent.learn, as a button</span></div></form>"""
        return busy_html + f"""
<div class="card"><div class="h0">On the wall.</div>
<div class="h0s mono">{v.get("video_id")} · the panel is watching</div>
{room_row}
<div class="foot"><a class="ghost" href="/channel">See it on Channel</a>
<div style="margin-left:auto;display:flex;gap:18px;align-items:flex-start">{learn}
<form method="post" action="/ui/run"><div style="text-align:right">
<input type="text" name="hint" value="{suggest_topic()}" style="min-width:280px">
<button class="go">Start next lap ▸</button><br>
<span style="font-size:12.5px;color:var(--sub)">pre-filled from <b>user:prefs</b> — the studio opens with your taste</span>
</div></form></div></div></div>"""

    # thumb approval?
    pend_thumb = drive.run(drive.pending(f"{st['run_id']}_thumb"))
    if pend_thumb and not any(a["kind"] == "thumb" for a in st["lineage"]["approvals"]):
        thumb = (st.get("thumb") or {}).get("ref", "")
        gen = "generated from your brief" if (st.get("thumb") or {}).get("generated") else "prebaked stand-in"
        return busy_html + f"""
<div class="card"><div class="h0">Ship this thumbnail?</div>
<div class="h0s">{gen} · renders keep cooking while you decide</div>
<img class="thumbprev" src="{thumb}">
<div class="foot">
<form method="post" action="/ui/rethumb"><button class="ghost">↻ Regenerate</button></form>
<form method="post" action="/ui/approve" style="margin-left:auto"><div style="text-align:right">
<button class="go">Approve ▸</button><br>
<span style="font-size:12.5px;color:var(--sub)">approve, and the lap finishes itself</span></div></form>
</div></div>"""

    if st.get("shots"):
        done = sum(1 for s in st["shots"] if s.get("status") in ("done", "fallback"))
        fallback = "" if b else """
<form method="post" action="/ui/finish"><div class="foot">
<span style="font-size:12.5px;color:var(--sub)">worker idle? run it again</span>
<button class="ghost">Finish ▸</button></div></form>"""
        return busy_html + f"""
<div class="card"><div class="h0">Rendering {done}/{len(st['shots'])}.</div>
<div class="h0s">every wait is a row — the worker delivers each one by id, then this lap finishes itself{" · three Veo shots, a minute or three each" if config.REAL_VIDEO and not broker.degraded() else ""}</div>{fallback}</div>"""

    if st.get("script"):
        ev_chips = ""
        for e in (st.get("brief") or {}).get("evidence", []):
            s_ = e.get("source", "")
            cls = "mm" if s_.startswith("memory#") else ("mg" if s_.startswith("graph#") else "")
            ev_chips += f'<span class="mchip {cls}">{s_}</span>'
        fallback = "" if b else """
<form method="post" action="/ui/render"><div class="foot">
<span style="font-size:12.5px;color:var(--sub)">renders idle? start them again</span>
<button class="ghost">Render ▸</button></div></form>"""
        return busy_html + f"""
<div class="card"><div class="h0">Direction cleared the policy gate.</div>
<div class="h0s">“{st['script']['title']}” — scripted quietly; renders start themselves</div>
<div class="made"><span class="k">EVIDENCE</span>{ev_chips or '<span class="mchip">none</span>'}</div>{fallback}</div>"""

    w = lap.where()
    if w["phase"] == "form":
        pay = w.get("payload") or {}
        cands = pay.get("candidates") or []
        idea = pay.get("idea", "")
        rows = ""
        for i, c in enumerate(cands, 1):
            ev = "".join(f'<span class="mchip {"mm" if e.get("source","").startswith("memory#") else ("mg" if e.get("source","").startswith("graph#") else "")}">{e.get("source","")}</span>'
                         for e in (c.get("evidence") or []))
            rows += f'''
<label class="drow"><input type="radio" name="pick" value="{i}" {"checked" if i == 1 else ""}>
<div><b>{c.get("title","")}</b><div class="h0s">{c.get("angle","")} {ev}</div></div></label>'''
        return busy_html + f"""
<div class="card"><div class="h0">Pick tonight's direction.</div>
<div class="h0s">researched from {"your idea: " + idea if idea else "the trends"} · the run is SUSPENDED on this form</div>
<form method="post" action="/ui/answer">
{rows}
<label class="drow"><input type="radio" name="pick" value="custom">
<div><b>write my own</b><input type="text" name="custom" placeholder="your direction, one line"></div></label>
<div class="foot"><span style="font-size:12.5px;color:var(--sub)">one function_response — then the policy gate runs by itself</span>
<button class="go">Continue ▸</button></div></form></div>"""

    if w["phase"] == "blocked":
        hits = ", ".join(w.get("hits") or [])
        return busy_html + f"""
<div class="card"><div class="h0">Blocked — by your own policy.</div>
<div class="h0s">“{w.get('direction','')}” contains <b>{hits}</b> (agent/policy_words.txt).
Nothing was scripted, rendered or paid.</div>
<form method="post" action="/ui/run"><div class="foot">
<input type="text" name="hint" placeholder="a different idea">
<button class="go">Start over ▸</button></div></form></div>"""

    return busy_html + '<div class="card"><div class="h0">Working…</div><div class="h0s">research is fanning out</div></div>'


# ── the way out ───────────────────────────────────────────────────────────
# Two controls, both destructive, so neither acts on the click that names it:
# the first POST only renders confirm_body() (with the meta refresh OFF, so it
# cannot bounce out from under the cursor), and only a second POST carrying
# confirm=yes actually stops or clears anything.

def escape_hatch() -> str:
    """End / Restart, under every Now page that has something to act on."""
    b, st = busy(), state.load()
    if not b and not st.get("run_id"):
        return ""                         # nothing running, no lap: no way out needed
    running = (f"{html.escape(b)} is running" if b else "nothing is running")
    return f"""
<div class="card" style="margin-top:18px">
<div class="h0" style="font-size:19px">A way out.</div>
<div class="h0s">{running} · both controls ask you to confirm on the next page —
this click stops nothing and clears nothing</div>
<div class="foot">
<form method="post" action="/ui/end"><button class="ghost">End the lap</button></form>
<form method="post" action="/ui/restart" style="margin-left:auto"><div style="text-align:right">
<button class="ghost">Restart — clear this lap</button><br>
<span style="font-size:12.5px;color:var(--sub)">python scripts/reset.py, as a button</span>
</div></form></div></div>"""


def confirm_body(action: str) -> str:
    """Step one of two. Says exactly what the second press will do - which pid
    dies, which files go - and offers a plain link back out."""
    b = busy()
    who = (f"python -m agent.{html.escape(b)} gets SIGTERM, then SIGKILL if it "
           f"is still there {GRACE_S:.0f}s later" if b else "nothing is running to stop")
    if action == "end":
        head, verb = "End this lap?", "Yes, end it ▸"
        what = (f'<div class="h0s" style="margin-top:9px">{who}. The lap itself is '
                'kept exactly where the worker left it — <span class="mono">runs/state.json</span>, '
                'the wall and your renders are all untouched, and you can pick it '
                'back up with Render or Finish.</div>')
    else:
        gone = ", ".join(str(p.relative_to(config.ROOT)) for p in reset.lap_paths())
        head, verb = "Restart — clear this lap?", "Yes, clear it and start over ▸"
        what = (f'<div class="h0s" style="margin-top:9px">{who}. Then this lap\'s files '
                'are archived into <span class="mono">runs/archive/</span> and removed: '
                f'<span class="mono">{html.escape(gone or "nothing on disk yet")}</span>.</div>'
                '<div class="h0s" style="margin-top:7px">Published history is NOT touched: '
                '<span class="mono">runs/wall.db</span> and the thumbnails and renders its '
                'rows point at all survive — the Channel keeps every video you have shipped.</div>')
    return f"""
<div class="card" style="border-left:4px solid #C97B6B">
<div class="h0">{head}</div>
<div class="h0s">this page does not refresh itself — nothing happens until you press below</div>
{what}
<div class="foot"><a class="ghost" href="/">Cancel — go back</a>
<form method="post" action="/ui/{action}" style="margin-left:auto">
<input type="hidden" name="confirm" value="yes">
<div style="text-align:right"><button class="danger">{verb}</button><br>
<span style="font-size:12.5px;color:var(--sub)">this one does it</span></div></form></div></div>"""


@app.get("/", response_class=HTMLResponse)
def now_page(request: Request):
    return page("now", now_body() + escape_hatch(),
                refresh="static" not in request.query_params)


@app.get("/channel", response_class=HTMLResponse)
def channel_page(request: Request):
    with db() as c:
        vids = c.execute("SELECT * FROM videos ORDER BY published_at DESC").fetchall()
        cards, made = [], ""
        for i, v in enumerate(vids):
            n = c.execute("SELECT COUNT(*) c, SUM(watched_ms) w FROM views WHERE video_id=?",
                          (v["id"],)).fetchone()
            views = n["c"] or 0
            avg = (n["w"] or 0) / (max(1, views) * v["duration_ms"]) * 100
            thumb = v["thumb_ref"] or "/static/art/thumb-clouds.png"
            ref = v["video_ref"] or ""
            playable = ref.endswith(".mp4") and (
                Path(__file__).parent / ref.lstrip("/")).exists()
            # thumbnail first - the video only appears when someone presses play
            media = (f'<div class="play" onclick="playv(this)"><img src="{thumb}">'
                     f'<span class="pb">▶</span><video src="{ref}" preload="none" playsinline></video></div>'
                     if playable else f'<img src="{thumb}">')
            cards.append(f"""<div class="v">{media}
<div class="vi"><span class="mchip" style="font-size:10px">LAP {v['lap']}</span>
<span class="vt">{v['title']}</span><span class="vp">{avg:.0f}<small>% · {views} views</small></span></div></div>""")
            if i == 0:
                lin = json.loads(v["lineage"])
                chips = "".join(f'<span class="mchip mm">{m}</span>' for m in lin.get("memory_refs", []))
                chips += "".join(f'<span class="mchip mg">{g}</span>' for g in lin.get("graph_refs", []))
                made = f'<div class="made"><span class="k">MADE WITH</span>{chips or "<span class=mchip>cold start — trends only</span>"}</div>'
    body = f"""<div class="card">
<div class="h0" style="font-size:19px">Your channel</div>
<div class="h0s" style="margin-bottom:18px">every video the agent has published · 24 panel viewers watch each one</div>
<div class="grid">{"".join(cards) or "<span class=note>nothing on the wall yet — finish a lap</span>"}</div>{made}</div>
<script>function playv(el){{el.classList.add('on');var v=el.querySelector('video');v.controls=true;v.play();}}</script>"""
    return page("channel", body, refresh="static" not in request.query_params)


@app.get("/state", response_class=HTMLResponse)
def state_page(request: Request):
    st = state.load()
    rid = st.get("run_id", "")
    open_calls = []
    for suffix in ("_wf", "_desk", "_thumb"):
        for cid, name, resp in (drive.run(drive.pending(f"{rid}{suffix}")) if rid else []):
            open_calls.append(f"{name} · id {str(cid)[:8]}… · open")
    sess = "<br>".join(open_calls) or "no open calls"
    prefs = st.get("prefs") or {}
    prefs_s = (f'<span class="hot">{st.get("direction") or prefs.get("last_direction", "")}</span>'
               if (st.get("direction") or prefs) else "—")
    grefs = st.get("graph_report", {}).get("queries", [])
    world = " · ".join(q["id"] for q in grefs if q.get("rows")) or "not connected yet"
    mem = st.get("memory_facts", [])
    mem_html = "".join(f'<div class="note">{m["fact"][:70]}</div>' for m in mem[:3]) or \
               '<div class="note">nothing learned yet — publish, then learn</div>'
    # the bank's CONNECT step is a one-time button on this row - the same
    # rule as the map: the button exists only while there is nothing to show
    from agent import memory as _memory
    bank_name = _memory.engine_name()
    bank_log = config.RUNS / "bank_run.log"
    if busy() == "bank":
        mem_html = ('<div class="note"><span class="dot"></span> connecting — creating an '
                    'Agent Engine to host the bank (~30s, one-time)…</div>')
    elif bank_name:
        tail = ""
        if bank_log.exists():          # the command's own lines, minus SDK warning noise
            keep = [l for l in bank_log.read_text().splitlines()
                    if l.strip() and not l.startswith("/") and "Warning" not in l
                    and not l.strip().startswith("_client")]
            tail = "\n".join(keep[-8:])
        mem_html = (f'<div class="note mono" style="font-size:11.5px">{bank_name}</div>'
                    + (f'<pre class="mono" style="font-size:11px;line-height:1.5;white-space:pre-wrap;'
                       f'margin:6px 0 4px;color:#5C5346">{tail}</pre>' if tail else "")
                    + mem_html)
    else:
        mem_html = ('<form method="post" action="/ui/bank"><div style="text-align:left">'
                    '<button class="go">Connect the bank ▸</button><br>'
                    '<span style="font-size:12px;color:var(--sub)">python -m agent.bank, as a button '
                    '— one-time, ~30s</span></div></form>')
    rows = f"""
<div class="row" style="opacity:.45"><img src="/static/art/gem-1.png"><div class="rn"><b>Turn</b><span>context window</span></div><div class="rv">gone when the turn ends</div><span class="life">seconds</span></div>
<div class="row"><img src="/static/art/gem-2.png"><div class="rn"><b>Session</b><span>sessions.db</span></div><div class="rv mono">{sess}</div><span class="life">outlives the process</span></div>
<div class="row"><img src="/static/art/gem-3.png"><div class="rn"><b>Run</b><span>state.json</span></div><div class="rv">lap {st.get('lap','—')} · direction {prefs_s}</div><span class="life">yours across runs</span></div>
<div class="row"><img src="/static/art/gem-4.png"><div class="rn"><b>World</b><span>BigQuery</span></div><div class="rv mono">{world}</div><span class="life">outlives every run</span></div>
<div class="row"><img src="/static/art/gem-5.png"><div class="rn"><b>Memory</b><span>Memory Bank</span></div><div class="rv">{mem_html}</div><span class="life">the channel's</span></div>
<div class="kill"><b>Kill anything.</b> These five survive.</div>"""
    return page("state", f'<div class="card" style="padding-top:20px">{rows}</div>', refresh="static" not in request.query_params)


# the three banners scripts/graph.sh prints, in order
GRAPH_STEPS = [("1/3 CONNECT + LOAD", "the dataset, the vendor pack, the graph DDL"),
               ("2/3 STORE", "your wall rows enter the world"),
               ("3/3 READ", "the readings your briefs cite")]


def graph_steps(log: str) -> str:
    """The same flow strip as the workflow map: a step turns solid when the
    script actually printed its banner - nothing here is on a timer."""
    out = []
    for i, (banner, why) in enumerate(GRAPH_STEPS):
        done = "done" if f"══ {banner} ══" in log else ""
        out.append(f'<div class="fs {done}"><div class="fd"></div>'
                   f'<div class="fl"><b>{banner.split("/3 ")[1]}</b><br>{why}</div></div>')
        if i < len(GRAPH_STEPS) - 1:
            out.append(f'<div class="fbar{" on" if done else ""}"></div>')
    return ('<div style="display:flex;align-items:flex-start;gap:6px">'
            + "".join(out) + '</div>')


def graph_readings() -> str:
    """runs/graph_report.json - written by bqgraph/report.py, the same payload
    the research node gets. The page never touches BigQuery itself."""
    f = config.RUNS / "graph_report.json"
    if not f.exists():
        return ""
    rep = json.loads(f.read_text())
    cards = []
    for q in rep.get("queries", []):
        rows = "".join(
            '<div class="note">' + " · ".join(f"{k} <b>{v}</b>" for k, v in r.items()
                                               if not k.endswith("_id"))
            + "</div>" for r in q["rows"][:5]) or '<div class="note">no rows yet</div>'
        cards.append(f'<div class="ql">{q["id"]} · {q["question"]} '
                     f'<span class="mchip mg">engine {q["engine"]}</span></div>{rows}')
    if rep.get("note"):
        cards.append(f'<div class="kill">{rep["note"]}</div>')
    return "".join(cards)


@app.get("/world", response_class=HTMLResponse)
def world_page(request: Request):
    """The BigQuery chapter as one button: it runs the very script the codelab
    prints, tails its output while it runs, then shows what it read back."""
    running = busy() == "graph"
    log_file = config.RUNS / "graph_run.log"
    log = log_file.read_text() if log_file.exists() else ""

    if running:
        head = ('<div class="busy"><span class="dot"></span>running '
                '<span class="mono">bash scripts/graph.sh</span> — creating the '
                'dataset, declaring the graph, querying it (~40s)</div>')
    else:
        label = "Run it again ▸" if log else "Build + read the graph ▸"
        head = (f'<form method="post" action="/ui/graph"><div class="foot">'
                f'<span class="mono" style="font-size:12px;color:var(--sub)">'
                f'runs: bash scripts/graph.sh</span>'
                f'<button class="go">{label}</button></div></form>')

    tail = (f'<div class="ql">LIVE OUTPUT</div><pre class="mono" style="font-size:12px;'
            f'line-height:1.55;white-space:pre-wrap;color:#5C5346;margin:0">'
            f'{log[-1700:]}</pre>' if log else
            '<div class="note">Nothing here yet. The button creates a dataset in '
            'YOUR project, loads the vendor pack, declares <span class="mono">'
            'taste_graph</span> over those tables, pushes your own rows in, and '
            'reads three questions back.</div>')

    body = (f'<div class="card"><div class="h0">The world graph</div>'
            f'<div class="h0s">BigQuery · dataset <span class="mono">{config.DATASET}</span>'
            f' — the rung that outlives this whole VM</div>'
            f'<div class="flow" style="margin-top:20px">{graph_steps(log)}</div>'
            f'{head}</div>'
            f'<div class="card" style="margin-top:18px">{graph_readings()}{tail}</div>')
    # ?static freezes the 4s auto-refresh - handy while reading a long log
    return page("world", body, refresh="static" not in request.query_params)


# ── buttons = the same CLIs the student runs ──
@app.post("/ui/graph")
def ui_graph():
    spawn_sh("graph", "scripts/graph.sh")
    return RedirectResponse("/world", status_code=303)


@app.post("/ui/run")
def ui_run(hint: str = Form("")):
    spawn("run", hint)
    return RedirectResponse("/", status_code=303)


@app.post("/ui/answer")
def ui_answer(pick: str = Form("1"), custom: str = Form("")):
    spawn("auto", "direction", "--pick", pick, "--custom", custom)
    return RedirectResponse("/", status_code=303)


@app.post("/ui/render")
def ui_render():
    spawn("render")
    return RedirectResponse("/", status_code=303)


@app.post("/ui/approve")
def ui_approve():
    spawn_force("auto", "ship")
    return RedirectResponse("/", status_code=303)


@app.post("/ui/rethumb")
def ui_rethumb():
    spawn_force("auto", "rethumb")
    return RedirectResponse("/", status_code=303)


@app.post("/ui/finish")
def ui_finish():
    spawn("finish")
    return RedirectResponse("/", status_code=303)


@app.post("/ui/learn")
def ui_learn():
    spawn("learn")
    return RedirectResponse("/", status_code=303)


@app.post("/ui/bank")
def ui_bank():
    spawn_logged("bank")
    return RedirectResponse("/state", status_code=303)


# ── the way out, as two buttons ──
# KEPT on End: everything. The lap stays exactly where the worker left it.
# KEPT on Restart: runs/wall.db (published history) and the thumbnails and
# renders under app/static/ that its rows point at - deleting either would
# leave the Channel page holding rows whose media is gone. scripts/reset.py
# owns the other list; both buttons call it, so neither can drift.
KEPT_ON_RESTART = ["runs/wall.db", "app/static/thumbs/", "app/static/renders/"]


@app.post("/ui/end")
def ui_end(confirm: str = Form("")):
    """Stop the worker. Leave every artifact of the lap alone."""
    if confirm != "yes":
        return HTMLResponse(page("now", confirm_body("end"), refresh=False))
    stopped = stop_worker()
    # a worker killed mid-write can leave half a JSON file behind, and
    # state.json is read by every page - so it never stays half-written
    moved = reset.quarantine(config.STATE, config.BROKER)
    cleared = [] if stopped.get("how") == "nothing was running" else ["runs/ui_busy.json"]
    _receipt("end", stopped, cleared=cleared,
             kept=["runs/state.json", "runs/broker.json", "runs/sessions.db",
                   "runs/wall.db"], moved=moved)
    return RedirectResponse("/", status_code=303)


@app.post("/ui/restart")
def ui_restart(confirm: str = Form("")):
    """Stop the worker, archive this lap's artifacts, clear them, start clean."""
    if confirm != "yes":
        return HTMLResponse(page("now", confirm_body("restart"), refresh=False))
    stopped = stop_worker()               # first, so nothing writes behind us
    out = reset.clear(archive=True)       # the SAME list scripts/reset.py uses
    # stop_worker() already took the busy slot; say so rather than let the
    # receipt imply it is still there
    gone = ([] if stopped.get("how") == "nothing was running" else ["runs/ui_busy.json"])
    _receipt("restart", stopped, cleared=gone + out["cleared"] + out["stuck"],
             kept=KEPT_ON_RESTART, archive=out["archive"])
    return RedirectResponse("/", status_code=303)
