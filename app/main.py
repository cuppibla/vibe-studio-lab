"""Vibe Studio - ONE server, two faces:
  · the Wall API (the platform contract the agent publishes to)
  · the console (Now / Channel / State) - a VIEW over the same durable state,
    whose every button just runs the same CLI the student runs. The button IS
    the delivered result.
"""
from __future__ import annotations

import json
import os
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
from world import simulator  # noqa: E402
# NOTE: `agent.lap` (→ agent.graph) is imported lazily inside now_body — in the
# carved starter the EDGES hole raises on import, and Studio must stay up to
# tell you which hole to fill instead of dying with the graph.

app = FastAPI(title="Vibe Studio")
app.mount("/static", StaticFiles(directory=Path(__file__).parent / "static"), name="static")

TRENDS = [
    {"topic": "tiny robots doing household chores (badly)", "heat": 91},
    {"topic": "pets reviewing kitchen gadgets", "heat": 84},
    {"topic": "desk toys with secret lives after midnight", "heat": 77},
    {"topic": "speedrunning the most boring chore you know", "heat": 66},
    {"topic": "kitchen science that looks illegal in 10 seconds", "heat": 58},
]

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
PY = str(config.ROOT / ".venv" / "bin" / "python")


def spawn(verb: str, *args) -> None:
    """Every button runs the SAME command the student runs. The button is the CLI.
    One at a time: a double-click must not start two runs."""
    if busy():
        return
    p = subprocess.Popen([PY, "-m", f"agent.{verb}", *args], cwd=config.ROOT,
                         stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    BUSY.write_text(json.dumps({"verb": verb, "pid": p.pid, "at": time.time()}))


def spawn_force(verb: str, *args) -> None:
    """Like spawn(), but for the buttons that must never be swallowed by a
    still-running worker (Approve/Regenerate). The previous job's pid rides
    along in the environment; the child waits for it before starting - see
    agent/auto.py _wait_for_pid."""
    p = subprocess.Popen([PY, "-m", f"agent.{verb}", *args], cwd=config.ROOT,
                         stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    BUSY.write_text(json.dumps({"verb": verb, "pid": p.pid, "at": time.time()}))


def spawn_sh(verb: str, script: str) -> None:
    """Same contract as spawn(), for the one step that IS a shell script:
    the World button runs `bash scripts/graph.sh`, unbuffered, into a log the
    page tails while it runs."""
    if busy():
        return
    log = (config.RUNS / "graph_run.log").open("w")
    env = {**os.environ, "PYTHONUNBUFFERED": "1",
           "PATH": f"{config.ROOT / '.venv' / 'bin'}:{os.environ.get('PATH', '')}"}
    proc = subprocess.Popen(["bash", script], cwd=config.ROOT, env=env,
                            stdout=log, stderr=subprocess.STDOUT)
    BUSY.write_text(json.dumps({"verb": verb, "pid": proc.pid, "at": time.time()}))


def busy() -> str | None:
    """Which button is still running, if any. Reaps first: a finished child
    stays in the process table as a zombie until someone waits on it, and a
    zombie answers signal 0 - it would look busy forever."""
    if not BUSY.exists():
        return None
    b = json.loads(BUSY.read_text())
    try:
        if os.waitpid(b["pid"], os.WNOHANG)[0] == b["pid"]:
            return None                      # it just finished; reaped now
    except ChildProcessError:
        pass                                 # not ours / already reaped
    try:
        os.kill(b["pid"], 0)
        return b["verb"]
    except OSError:
        return None


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
    busy_html = f'<div class="busy"><span class="dot"></span>{b} is running — this page refreshes itself</div>' if b else ""
    if st.get("run_id"):
        # the live map of the workflow (nodes+edges dumped from the real
        # Workflow object), above every card of a running lap
        from app import flowmap
        busy_html += flowmap.render(st, lap.where().get("phase", ""), MASCOT)

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
        return busy_html + f"""
<div class="card"><div class="h0">On the wall.</div>
<div class="h0s mono">{v.get("video_id")} · the panel is watching</div>
{room_row}
<div class="foot"><a class="ghost" href="/channel">See it on Channel</a>
<form method="post" action="/ui/learn" style="margin-left:auto"><div style="text-align:right">
<button class="go">Learn from the audience ▸</button><br>
<span style="font-size:12.5px;color:var(--sub)">python -m agent.learn, as a button</span></div></form>
<form method="post" action="/ui/run"><div style="text-align:right">
<input type="text" name="hint" value="{suggest_topic()}" style="min-width:280px">
<button class="go">Start next lap ▸</button><br>
<span style="font-size:12.5px;color:var(--sub)">pre-filled from <b>user:prefs</b> — the studio opens with your taste</span>
</div></form></div></div>"""

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
<div class="h0s">every wait is a row — the worker delivers each one by id, then this lap finishes itself</div>{fallback}</div>"""

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


@app.get("/", response_class=HTMLResponse)
def now_page(request: Request):
    return page("now", now_body(), refresh="static" not in request.query_params)


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
            media = (f'<video src="{ref}" poster="{thumb}" controls preload="none"></video>'
                     if playable else f'<img src="{thumb}">')
            cards.append(f"""<div class="v">{media}
<div class="vi"><span class="mchip" style="font-size:10px">LAP {v['lap']}</span>
<span class="vt">{v['title']}</span><span class="vp">{avg:.0f}<small>% · {views} views</small></span></div></div>""")
            if i == 0:
                lin = json.loads(v["lineage"])
                ch = state.load().get("choices") or {}
                chips = "".join(f'<span class="mchip">{x}</span>' for x in
                                [ch.get("character", ""), ch.get("style", "")] if x)
                chips += "".join(f'<span class="mchip mm">{m}</span>' for m in lin.get("memory_refs", []))
                chips += "".join(f'<span class="mchip mg">{g}</span>' for g in lin.get("graph_refs", []))
                made = f'<div class="made"><span class="k">MADE WITH</span>{chips or "<span class=mchip>cold start — trends only</span>"}</div>'
    body = f"""<div class="card">
<div class="h0" style="font-size:19px">Your channel</div>
<div class="h0s" style="margin-bottom:18px">every video the agent has published · 24 panel viewers watch each one</div>
<div class="grid">{"".join(cards) or "<span class=note>nothing on the wall yet — finish a lap</span>"}</div>{made}</div>"""
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
