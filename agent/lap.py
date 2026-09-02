"""Lap driver helpers shared by the CLIs and the Studio app."""
import json
import time

from . import config, drive, state
from .graph import wf


def wf_sid() -> str:
    return f"{state.load()['run_id']}_wf"


def start_lap(hint: str) -> str:
    """Fresh run scaffolding; returns the kickoff message for the first leg."""
    from world import broker, platform
    if not wf.edges:
        raise NotImplementedError(
            "TODO: EDGES — the graph has no edges yet. Open agent/graph.py, "
            "delete the TODO line and uncomment the base edge list under it "
            "(Codelab: 'the EDGES hole').")
    st = state.load()
    creds = st.get("creds") or platform.join("annie")
    run_id = f"run_{int(time.time())}"
    broker.reset()
    state.save({
        "run_id": run_id, "lap": st.get("next_lap", 1),
        "next_lap": st.get("next_lap", 1), "creds": creds, "hint": hint,
        "last_learn_flags": st.get("last_learn_flags"),   # survives lap resets
        "lineage": {"evidence": [], "memory_refs": [], "graph_refs": [],
                    "shots": [], "repair": [], "deadline": [], "approvals": [],
                    "gates": {}},
    })
    prefs = drive.run(drive.ensure_user_state(f"{run_id}_wf")).get("user:prefs")
    if prefs:
        state.update(prefs=prefs)
        print(f"  prefs found (user:prefs): {prefs}")
    return f"Plan tonight's video. Creator idea: {hint or '(none — you choose)'}"


def latest_proposal() -> str:
    """The topic gate's most recent message (for the Studio proposal card)."""
    async def _get():
        s = await drive.svc().get_session(app_name=config.APP, user_id=config.USER,
                                          session_id=wf_sid())
        if not s:
            return ""
        for ev in reversed(s.events):
            if getattr(ev, "author", "") == "topic_gate":
                msg = getattr(ev, "message", None) or getattr(ev, "content", None)
                for p in (getattr(msg, "parts", None) or []):
                    if getattr(p, "text", None):
                        return p.text.strip()
        return ""
    return drive.run(_get())


def leg(text_or_answer) -> None:
    """One leg of the workflow session; prints agent text as it streams."""
    sid = wf_sid()
    if isinstance(text_or_answer, str):
        out = drive.run(drive.say(wf, sid, text_or_answer))
    else:
        cid, name, response = text_or_answer
        out = drive.run(drive.answer(wf, sid, cid, name, response))
    if out:
        print(out.strip()[:600])


def where() -> dict:
    """Phase detection for prompts + the Studio Now card."""
    st = state.load()
    if not st.get("run_id"):
        return {"phase": "idle"}
    if st.get("published"):
        return {"phase": "published", "video": st["published"]}
    if st.get("blocked") and not st.get("script"):
        return {"phase": "blocked", **st["blocked"]}
    if st.get("script"):
        return {"phase": "scripted", "title": st["script"]["title"]}
    pend = drive.run(drive.pending(wf_sid()))
    for cid, name, resp in pend:
        if name == "adk_request_input":
            return {"phase": "form", "call": (cid, name),
                    "message": resp.get("message"), "schema": resp.get("response_schema"),
                    "payload": resp.get("payload")}
    return {"phase": "proposal"}   # task gate holds the floor: reply with agent.say


def print_where() -> None:
    w = where()
    p = w["phase"]
    if p == "form":
        pay = w.get("payload") or {}
        print(f"⏸  FORM — {w['message']}")
        for i, c in enumerate(pay.get("candidates") or [], 1):
            print(f"   {i} · {c.get('title')}")
        print('   answer: python -m agent.answer --pick 1   (or --pick custom --custom "…")')
    elif p == "proposal":
        print("⏸  PROPOSAL — the topic gate is chatting with you.")
        print('   push back or accept: python -m agent.say "…"')
    elif p == "blocked":
        print(f"⛔ blocked by your own policy ({', '.join(w.get('hits', []))}) — "
              "start a new lap with a different direction")
    elif p == "scripted":
        print(f"✓ script ready: {w['title']!r} — next: python -m agent.render")
    elif p == "published":
        print(f"✓ published: {w['video']}")
    else:
        print("idle — start with: python -m agent.run \"a hint\"")
