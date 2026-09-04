"""The driver-owned join. ADK delivers answers; counting "done" is YOURS:
no render pending AND the human approved the thumbnail -> post-production."""
import json

from . import drive, post, state
from .desk import prompt_medic, render_desk


def desk_sid(st) -> str:
    return f"{st['run_id']}_desk"


def already_answered(st, job_id) -> bool:
    return job_id in st.setdefault("answered_jobs", [])


def mark_answered(job_id) -> None:
    st = state.load()
    st.setdefault("answered_jobs", []).append(job_id)
    state.save(st)


def handle_done(cid, name, resp, job) -> None:
    print(f"── result delivered: {job['id']} ──")
    st = state.load()
    drive.run(drive.answer(render_desk, desk_sid(st), cid, name,
                           {"status": "done", "shot": resp["shot"], "url": job["url"]}))
    _record_url(resp["shot"], job["url"], "done")
    mark_answered(job["id"])


def handle_failed(cid, name, resp, job) -> None:
    """qc FAIL -> prompt_medic rewrites -> retake submitted (repair INSIDE the wait)."""
    print(f"── qc FAIL: {job['id']} ({job['reason']}) -> prompt_medic ──")
    st = state.load()
    run_id = st["run_id"]
    fix = json.loads(drive.run(drive.say(
        prompt_medic, f"{run_id}_medic_{job['idx']}",
        f"Original prompt: {resp['shot']}\nFailure: {job['reason']}")))
    st = state.load()
    st["lineage"]["repair"].append(
        {"original": resp["shot"], "reason": job["reason"],
         "new_prompt": fix["new_prompt"], "what_changed": fix["what_changed"]})
    state.save(st)
    print(f"  medic: {fix['what_changed'][:80]}")
    drive.run(drive.answer(render_desk, desk_sid(st), cid, name,
                           {"status": "replaced", "shot": resp["shot"],
                            "note": "retake submitted separately"}))
    out = drive.run(drive.say(
        render_desk, desk_sid(st),
        f"Retake for the failed shot — render this instead:\n{fix['new_prompt']}"))
    print(f"  desk: {out!r}")
    _record_retake(resp["shot"], fix["new_prompt"])
    mark_answered(job["id"])


def handle_deadline(cid, name, resp, job) -> None:
    print(f"── deadline: {job['id']} replaced by prebaked stand-in ──")
    st = state.load()
    drive.run(drive.answer(render_desk, desk_sid(st), cid, name,
                           {"status": "done", "shot": resp["shot"],
                            "url": "prebaked/fallback.mp4", "fallback": True}))
    st = state.load()
    st["lineage"]["deadline"].append({"shot": resp["shot"], "job": job["id"]})
    state.save(st)
    _record_url(resp["shot"], "prebaked/fallback.mp4", "fallback")
    mark_answered(job["id"])


def try_finish() -> dict | None:
    """THE JOIN: no pending renders AND the thumb approved -> post-production."""
    st = state.load()
    still = drive.run(drive.pending(desk_sid(st)))
    human_ok = any(a["kind"] == "thumb" for a in st["lineage"]["approvals"])
    if still:
        return None
    if not human_ok:
        print("renders complete — waiting on HUMAN (thumbnail). "
              "Doorbell: python -m agent.approve  (or the Studio button)")
        return None
    shots = st.get("shots") or []
    landed = [s for s in shots if s.get("url")]
    print(f"── join complete (renders {len(landed)}/{len(shots)} + human) "
          f"-> post-production ──")
    st["lineage"]["shots"] = [_lineage_shot(s) for s in shots]
    state.save(st)
    result = drive.run(post.run_post(st["run_id"]))
    print(f"PUBLISHED: {result}")
    st = state.load()
    st["next_lap"] = st["lap"] + 1
    state.save(st)
    if result.get("published"):
        # the room, silently: if Setup pointed .env at one, the same press
        # premieres there too - and a room failure can never fail the lap
        from . import premiere
        room = premiere.publish_to_room(state.load())
        state.update(room=room)
        if room.get("url"):
            print(f"  the room can see you: {room['url']}")
    return result


def _lineage_shot(s: dict) -> dict:
    """One shot, as the AUDIT TRAIL records it.

    A shot only has a `url` once the farm actually delivered something: the two
    success paths in world/broker.py write one, and every failure path there
    sets status="failed" (usually with a `reason`) and leaves `url` absent.

    So `url` is optional, and its absence is not a hole to paper over with an
    empty string - an empty string in a url field reads like a url that did not
    render, which is a different and untrue story. A shot that never rendered is
    recorded as failed WITH the reason the farm gave, and with no url key at
    all. The lineage is the lab's evidence; it says what happened.

    The delivered shape is byte-for-byte what it always was, so a lap where
    every shot lands produces exactly the lineage it produced before.
    """
    if s.get("url"):
        row = {"prompt": s.get("prompt", ""), "url": s["url"],
               "status": s.get("status", "done")}
    else:
        row = {"prompt": s.get("prompt", ""),
               "status": s.get("status") or "failed",
               "reason": s.get("reason") or "no result was ever delivered"}
    if s.get("retake_of"):
        row["retake_of"] = s["retake_of"]
    return row


def shot_tally(st: dict) -> tuple[int, int]:
    """(delivered, total) for the current lap - what the join actually joined."""
    shots = st.get("shots") or []
    return sum(1 for s in shots if s.get("url")), len(shots)


def _record_url(shot_prompt, url, status):
    st = state.load()
    for s in st.get("shots") or []:
        if s.get("prompt") == shot_prompt or s.get("retake_of") == shot_prompt:
            s["url"], s["status"] = url, status
            s.pop("reason", None)      # it landed: an earlier failure's reason
            s.pop("failed_before", None)   # must not follow it into the lineage
    state.save(st)


def _record_retake(original_prompt, new_prompt):
    st = state.load()
    for s in st.get("shots") or []:
        if s.get("prompt") == original_prompt:
            s["prompt"] = new_prompt
            s["retake_of"] = original_prompt
            s["status"] = "retake_submitted"
    state.save(st)
