"""The lap, as a list of stages - read from what the run actually wrote.

Same two rules as the workflow map next door (app/flowmap.py), because a
learner should be able to trust both pictures the same way:

  1 · The vocabulary is not invented here. Every stage below is a step the
      lab already names somewhere else - a `lap.where()` phase, a worker verb
      (`agent.run` / `agent.render` / `agent.finish`), a graph node, or a key
      the run writes into `runs/state.json`. The labels are the codelab's own
      words so the list reads like the chapter the student is standing in.

  2 · Every status is DERIVED from a durable artifact - runs/state.json,
      runs/broker.json, runs/<verb>_run.log, runs/ui_last.json. Nothing is
      recorded twice and nothing is remembered in the process, so the list
      says the same true thing after you kill the server and reload. That is
      the whole thesis of this lab: the process may die, the state may not.

The three things a learner most needs to see - a stage that FAILED, a Veo
retry, and a run that degraded to the prebaked clock - are read straight from
the artifacts the existing fixes already write. `failed_card()` and
`farm_note()` in app/main.py still render the detail; this list is the map
that says WHICH stage they belong to.
"""
from __future__ import annotations

import html
import json
import os
import shutil

from agent import config as _config


def _have_ffmpeg() -> bool:
    """ffmpeg on PATH. Cheap (a PATH scan), and read fresh every render so the
    row goes green the moment the learner installs it - no server restart."""
    return bool(shutil.which("ffmpeg"))


def _room_configured() -> bool:
    """Did Setup point .env at a room? Read at render time for the same reason
    agent/premiere.py reads it at call time: a .env filled during Setup must be
    honored without restarting anything."""
    return bool(os.environ.get("VIBETUBE_URL", "").strip()
                and os.environ.get("VIBETUBE_EVENT", "").strip())

# ── the vocabulary ───────────────────────────────────────────────────────────
# key · label · the one-line gloss, in the codelab's voice
STAGES = [
    ("research", "Researching your topic",         "four feeds, joined into one cited bundle"),
    ("direction","You pick the direction",         "the form — the run suspends on you"),
    ("policy",   "Safety check on your direction", "OK or BLOCK, before any money is spent"),
    ("script",   "Video prompt",                   "the title, the description and 3 shot prompts"),
    ("render",   "Video generation",               "one Veo shot per prompt, plus your thumbnail"),
    ("thumb",    "You approve the thumbnail",      "the human wait"),
    ("join",     "Waiting for all 3 shots",        "every render delivered, and you"),
    ("publish",  "Publish",                        "eval backstop, then the side effect"),
    ("room",     "Premiering to VibeTube",         "the room's wall, if Setup joined one"),
]

# Which worker verb drives which stage - used to blame the right row when a
# worker exits non-zero. `auto` covers several buttons, so it is resolved
# against the lap's own position (see _blame).
VERB_STAGE = {
    "run": "research",
    "render": "render",
    "finish": "join",
    "auto": None,          # direction / ship / rethumb - decided by position
}

# The same table read backwards: the stage a Retry re-runs, and the verb it
# runs to do it. Derived from VERB_STAGE rather than written out again, so the
# two can never drift. `auto` maps to None (it drives three different buttons,
# resolved by position) and therefore contributes no stage - which is the right
# answer: none of the rows it touches can be re-run on their own.
STAGE_VERB = {stage: verb for verb, stage in VERB_STAGE.items() if stage}

# The label for a key, for anything that has to NAME a stage back to the user
# (the confirm page, the receipt). Same list, one source.
STAGE_LABEL = {key: label for key, label, _ in STAGES}

PASS, NOW, FAIL, RETRY, DEGRADED, BLOCKED, SKIP, IDLE, STALL, WAIT = (
    "pass", "now", "fail", "retry", "degraded", "blocked", "skip", "idle",
    "stall", "wait")
# NOW means a WORKER is executing; WAIT means the lap is suspended on the
# human. The difference matters after a restart: a killed worker leaves
# nothing running, but a human wait is a durable row and is still genuinely
# open - which is the lesson the lab is here to teach. `⏸` is the mark
# agent/lap.py print_where() and agent/render.py already use for it.


# ── the artifacts ────────────────────────────────────────────────────────────

def _broker() -> dict:
    """runs/broker.json - the farm's own record, shared by every worker."""
    try:
        return json.loads(_config.BROKER.read_text())
    except (OSError, ValueError):
        return {}


def _last() -> dict:
    """runs/ui_last.json - {verb, code}, written when busy() reaps a worker."""
    try:
        return json.loads((_config.RUNS / "ui_last.json").read_text())
    except (OSError, ValueError):
        return {}


def log_tail(verb: str, n: int = 6) -> list[str]:
    """The last n non-blank lines of runs/<verb>_run.log.

    One implementation, two readers: app/main.py `failed_card()` renders the
    full tail in its card, and the stage row shows the last line as the
    reason. Keeping it here means the two can never disagree.
    """
    log = _config.RUNS / f"{verb}_run.log"
    try:
        return [l for l in log.read_text(errors="replace").splitlines() if l.strip()][-n:]
    except OSError:
        return []


def farm_lines(verbs=("render", "finish")) -> list[str]:
    """The farm's own `[farm] …` chatter, from the worker logs it is printed to.

    world/broker.py prints its retry and failover story here and nowhere else,
    so this is where a retry that is happening RIGHT NOW is visible - before
    it has resolved into a broker.json field.
    """
    out = []
    for v in verbs:
        out += [l for l in log_tail(v, 400) if "[farm]" in l]
    return out


def veo_retry(bk: dict) -> str:
    """Is a Veo call mid-retry, or did one just happen? Two durable traces:

      · broker.json job['op_errors'] == 1 - a poll failed once and the run has
        exactly one retry left. This is a field, so it survives a restart.
      · the `[farm] veo submit attempt 1/2 failed` line in the worker log -
        the submit retry is over in about a second, too fast to leave a field,
        but the line stays on disk.

    Returns (in_flight, sentence). `in_flight` is True only while a retry is
    genuinely outstanding - a retry that already RECOVERED is history worth
    printing, not a reason to keep the row spinning.
    """
    for j in bk.get("jobs", []):
        if j.get("real") and j.get("op_errors") == 1 and j.get("status") == "queued":
            return True, f"Veo failed on {j.get('id', 'a shot')}, retrying (1 of 1)"
    for l in reversed(farm_lines()):
        if "recovered on the retry" in l:
            return False, "Veo failed once, recovered on the retry"
        if "attempt 1/2 failed" in l:
            return True, "Veo failed, retrying (1 of 1)"
    return False, ""


# ── deriving each stage's status ─────────────────────────────────────────────

def _blame(st: dict, done: dict) -> tuple[str, str] | None:
    """A worker exited non-zero - whose row is that?

    ui_last.json names the verb; VERB_STAGE maps it to the stage it drives.
    `auto` drives three different buttons, and a verb can also die after its
    own stage already passed (finish, twice), so the blame falls on the first
    stage that has NOT passed - which is exactly where the lap is stuck.
    """
    f = _last()
    if not f.get("code"):
        return None                       # exited 0, or never ran
    verb = f.get("verb", "")
    want = VERB_STAGE.get(verb, "__none__")
    if want == "__none__":
        return None                       # learn / bank / graph - not lap stages
    if want and not done.get(want):
        target = want
    else:
        target = next((k for k, _, _ in STAGES if not done.get(k)), None)
    if not target:
        return None
    tail = log_tail(verb, 1)
    why = tail[0] if tail else f"exited {f['code']}"
    return target, f"python -m agent.{verb} exited {f['code']} · {why}"


def stage_states(st: dict, phase: str, busy_verb: str | None,
                 pend_thumb: bool = False) -> list[dict]:
    """The whole list: one dict per stage, every field read from an artifact.

    `st` is runs/state.json, `phase` is `lap.where()['phase']`, `busy_verb` is
    whatever `busy()` in app/main.py just returned (it reaps, so only it may
    decide that something is actually alive). Nothing else is consulted.
    """
    bk = _broker()
    dg = bk.get("degraded")
    lin = st.get("lineage") or {}
    gates = lin.get("gates") or {}
    shots = st.get("shots") or []
    room = st.get("room") or {}

    # ── what has definitely happened, per the artifacts ──
    approved = any(a.get("kind") == "thumb" for a in (lin.get("approvals") or []))
    policy = gates.get("policy") or {}
    ev = gates.get("eval") or {}
    ev_failed = bool(ev) and not all((ev.get("checks") or {}).values())
    delivered = [s for s in shots if s.get("status") in ("done", "fallback")]
    all_delivered = bool(shots) and len(delivered) == len(shots)
    # A shot the farm gave up on: world/broker.py sets status="failed" on every
    # failure path and leaves no url behind. The reason it wrote is the only
    # honest thing this list can say about a shot that never rendered.
    failed = [str(s.get("reason") or "") for s in shots if s.get("status") == "failed"]

    done = {
        "research":  bool(st.get("brief") or st.get("candidates")),
        "direction": bool(st.get("direction")),
        "policy":    bool(policy),
        "script":    bool(st.get("script")),
        "render":    bool(shots),
        "thumb":     approved,
        "join":      all_delivered and approved,
        "publish":   bool(st.get("published")),
        "room":      bool(room),
    }
    blame = _blame(st, done)

    rows = []
    for key, label, sub in STAGES:
        status, note = IDLE, ""

        # ── research ──
        if key == "research":
            if done["research"]:
                status, note = PASS, f"{len(st.get('candidates') or [])} directions proposed"
            elif st.get("run_id"):
                status = NOW if (busy_verb == "run" or phase == "proposal") else STALL
                note = "the four feeds are fanning out"

        # ── direction ──
        elif key == "direction":
            if done["direction"]:
                status, note = PASS, st.get("direction", "")
            elif phase == "form":
                status, note = WAIT, "the run is SUSPENDED on the form — a row, not a process"

        # ── the policy gate ──
        elif key == "policy":
            if st.get("blocked"):
                status = BLOCKED
                note = "BLOCK — " + ", ".join(st["blocked"].get("hits") or [])
            elif policy:
                status = PASS if policy.get("ok") else BLOCKED
                note = "OK" if policy.get("ok") else "BLOCK — " + ", ".join(policy.get("hits") or [])

        # ── the script ──
        elif key == "script":
            if done["script"]:
                status, note = PASS, (st.get("script") or {}).get("title", "")
            elif done["policy"] and policy.get("ok"):
                status, note = NOW, "writing the title, description and shot prompts"

        # ── the render farm ──
        elif key == "render":
            if shots:
                n, tot = len(delivered), len(shots)
                spinning, why = veo_retry(bk)
                if dg:
                    status = DEGRADED
                    note = (f"{n}/{tot} delivered on the PREBAKED clock — "
                            "stand-ins, not Veo output")
                elif spinning:
                    status, note = RETRY, why
                elif all_delivered:
                    # a retry that recovered is part of the story, not a state
                    status = PASS
                    note = f"{n}/{tot} shots delivered" + (f" · {why}" if why else "")
                elif failed and st.get("published"):
                    # the lap FINISHED short. The farm is not still working and
                    # this row is not stalled - it is done, and one shot is gone.
                    status = FAIL
                    note = (f"{n}/{tot} shots delivered · {len(failed)} failed"
                            + (f" — {failed[0]}" if failed[0] else ""))
                else:
                    status = NOW if busy_verb in ("render", "finish") else STALL
                    note = (f"{n}/{tot} delivered" + (f" · {why}" if why else "")
                            + (f" · {len(failed)} failed" if failed else ""))
            elif done["script"]:
                status = NOW if busy_verb == "render" else IDLE
                note = "submitting the shots in ONE turn"

        # ── your thumbnail ──
        elif key == "thumb":
            if approved:
                status, note = PASS, "approved"
            elif pend_thumb or st.get("thumb"):
                status, note = WAIT, "approve it and the lap finishes itself"

        # ── the join ──
        elif key == "join":
            retakes, late = len(lin.get("repair") or []), len(lin.get("deadline") or [])
            extra = []
            if retakes:
                extra.append(f"{retakes} retake{'s' if retakes > 1 else ''} (qc FAIL → medic)")
            if late:
                extra.append(f"{late} deadline stand-in{'s' if late > 1 else ''}")
            if failed:
                extra.append(f"{len(failed)} shot{'s' if len(failed) > 1 else ''} failed")
            if done["join"]:
                status = PASS
                note = "renders complete + human approved" + (" · " + ", ".join(extra) if extra else "")
            elif approved and st.get("published"):
                # The join DID complete - it just joined fewer shots than it
                # asked for. Without this the row sits on "2/3 in" forever
                # behind a lap that finished minutes ago: a silent gap.
                status = PASS
                note = (f"finished with {len(delivered)} of {len(shots)} shots"
                        + (" · " + ", ".join(extra) if extra else ""))
            elif shots:
                status = NOW if busy_verb == "finish" else (
                    STALL if delivered else IDLE)
                note = (f"{len(delivered)}/{len(shots)} in"
                        + (" · " + ", ".join(extra) if extra else "")
                        + ("" if approved else " · still waiting on the thumbnail"))

        # ── the wall ──
        elif key == "publish":
            if st.get("published"):
                status = PASS
                note = str((st.get("published") or {}).get("video_id", ""))
            elif ev_failed:
                bad = [k for k, v in (ev.get("checks") or {}).items() if not v]
                status, note = FAIL, "eval gate FAIL — " + ", ".join(bad)
            elif done["join"]:
                status, note = NOW, "editor → eval backstop → publish"

        # ── the room ──
        elif key == "room":
            if room.get("url"):
                status, note = PASS, "premiered to the room"
            elif room.get("skipped") == "no room configured":
                status, note = SKIP, "no room configured — self-paced, nothing depends on it"
            elif room.get("skipped"):
                status, note = FAIL, "premiere failed — " + str(room["skipped"])
            elif not _room_configured():
                status, note = SKIP, "no room configured — self-paced, nothing depends on it"
            elif not _have_ffmpeg():
                # Said HERE, at the top of the lap, instead of on the wall card
                # forty minutes later. The premiere is the one step that cannot
                # degrade - no ffmpeg, no mp4, no room - so the row says it will
                # be skipped before the learner spends the lap finding out.
                status = DEGRADED
                note = ("ffmpeg is not installed — the premiere cut cannot be "
                        "packaged and the room will be skipped (the lap still "
                        "publishes) · fix: ./setup_codelab.sh")
            elif st.get("published"):
                status, note = NOW, "packaging the premiere cut"

        # a dead worker overrides whatever the artifacts implied for its row
        if blame and blame[0] == key and status in (NOW, IDLE, STALL):
            status, note = FAIL, blame[1]

        # One row says one thing once. Several rows can derive a note that is
        # word-for-word their own static subtitle - the script row always does
        # while it is running, and any row whose note comes from the model or
        # the user (direction, script title) can land on it too. Printed twice,
        # it reads like the stage happened twice.
        if note.strip().casefold() == sub.strip().casefold():
            note = ""

        rows.append({"key": key, "label": label, "sub": sub,
                     "status": status, "note": note})
    return rows


# ── which rows may be re-run on their own ───────────────────────────────────
# A stage is worth re-running when it DIED (FAIL), when it is sitting there
# with no worker behind it (STALL), or when it fell back to the prebaked clock
# (DEGRADED). Deliberately not: PASS and NOW (fine, or already moving), RETRY
# (a retry is in flight - a second one would race it), WAIT (the human IS the
# next step; that row's own form is the retry), IDLE, SKIP and BLOCKED (nothing
# has happened yet, or a verdict was reached and re-running changes nothing).
RERUNNABLE = (FAIL, STALL, DEGRADED)


def retry_verb(row: dict) -> str | None:
    """The worker `Retry` re-runs for this row - or None if this row offers no
    Retry at all.

    Two gates, both read off things that already exist: the row has to be in a
    re-runnable state, and STAGE_VERB (i.e. VERB_STAGE backwards) has to name a
    verb that drives it. Rows with no verb of their own are never offered the
    button, because there is nothing to re-run in isolation - see RETRY.md for
    the list and the reason for each.

    Note it is always the row's OWN verb, never whichever verb happened to die.
    `_blame` can pin a dead worker on a row further down the lap, and a button
    that says "Retry" on the render row while quietly running agent.finish
    would be exactly the sort of thing this list exists to stop.
    """
    if row.get("status") not in RERUNNABLE:
        return None
    return STAGE_VERB.get(row.get("key"))


def retryable(st: dict, phase: str, busy_verb: str | None,
              pend_thumb: bool = False) -> dict:
    """{stage key: verb} for every row offering Retry right now.

    The page draws its buttons from this and the POST handler validates against
    it, so a stale form cannot make the server run something the row was not
    offering by the time it arrived.
    """
    out = {}
    for r in stage_states(st, phase, busy_verb, pend_thumb):
        v = retry_verb(r)
        if v:
            out[r["key"]] = v
    return out


def retry_form(key: str, label: str, verb: str) -> str:
    """One Retry button, on one row. Plain form -> POST -> 303, the same idiom
    as every other button in this app, and no JavaScript anywhere.

    The button NAMES the stage and the command, so there is never a question
    about which row it belongs to or what it is about to run. The POST only
    reaches a confirm page; nothing is re-run on this click.
    """
    return (f'<form class="stf" method="post" action="/ui/retry">'
            f'<input type="hidden" name="stage" value="{html.escape(key, quote=True)}">'
            f'<button class="stbtn">&#8635; Retry &#8220;{html.escape(label)}&#8221; '
            f'&mdash; python -m agent.{html.escape(verb)}</button></form>')


# ── the markup ───────────────────────────────────────────────────────────────

MARK = {PASS: "✓", NOW: "●", FAIL: "✕", RETRY: "↻", DEGRADED: "▲",
        BLOCKED: "⛔", SKIP: "–", IDLE: "○", STALL: "◍", WAIT: "⏸"}
WORD = {PASS: "passed", NOW: "running", FAIL: "FAILED", RETRY: "retrying",
        DEGRADED: "degraded", BLOCKED: "blocked", SKIP: "skipped", IDLE: "",
        STALL: "stalled — no worker", WAIT: "waiting on you"}


def render(st: dict, phase: str, busy_verb: str | None,
           pend_thumb: bool = False) -> str:
    """The card. Same grammar as every other card on the page: `card`, `h0`,
    `h0s`, `mono` - and the stage classes added to CSS next to the flow strip.

    Everything that came from a log, a title or the room is html-escaped: a
    traceback and a video title are both going straight into a page.
    """
    rows = stage_states(st, phase, busy_verb, pend_thumb)
    if not st.get("run_id"):
        body = ('<div class="h0s" style="margin-top:10px">No lap yet — start one and '
                'every stage below lights up from what the run writes to disk.</div>')
    else:
        body = ""
    out = []
    for r in rows:
        word = WORD[r["status"]]
        badge = (f'<span class="stw">{html.escape(word)}</span>' if word else "")
        note = (f'<div class="stn mono">{html.escape(r["note"])}</div>'
                if r["note"] else "")
        # the one control that lives ON a row: re-run just this stage. Only the
        # rows retry_verb() vouches for get one.
        v = retry_verb(r)
        retry = retry_form(r["key"], r["label"], v) if v else ""
        out.append(
            f'<div class="stg {r["status"]}">'
            f'<span class="stm">{MARK[r["status"]]}</span>'
            f'<div class="stb"><div class="stl">{html.escape(r["label"])}{badge}</div>'
            f'<div class="sts">{html.escape(r["sub"])}</div>{note}{retry}</div></div>')

    room = st.get("room") or {}
    link = ""
    url = str(room.get("url") or "")
    if url.startswith(("http://", "https://")):
        link = (f'<div class="h0s" style="margin-top:12px">watch it with everyone else — '
                f'<a class="stk" href="{html.escape(url, quote=True)}" target="_blank">'
                f'{html.escape(url)} ↗</a></div>')

    return f"""
<div class="card" style="margin-bottom:18px">
<div class="h0" style="font-size:19px">This lap, stage by stage.</div>
<div class="h0s">every line below is read from what the run wrote to disk — kill the
server and reload, and it still says the same thing</div>{body}
<div class="stlist">{"".join(out)}</div>{link}</div>"""
