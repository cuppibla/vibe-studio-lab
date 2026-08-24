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
    print("── join complete (renders N/N + human) -> post-production ──")
    st["lineage"]["shots"] = [{"prompt": s["prompt"], "url": s["url"],
                               "status": s["status"]} for s in st["shots"]]
    state.save(st)
    result = drive.run(post.run_post(st["run_id"]))
    print(f"PUBLISHED: {result}")
    st = state.load()
    st["next_lap"] = st["lap"] + 1
    state.save(st)
    return result


def _record_url(shot_prompt, url, status):
    st = state.load()
    for s in st["shots"]:
        if s["prompt"] == shot_prompt or s.get("retake_of") == shot_prompt:
            s["url"], s["status"] = url, status
    state.save(st)


def _record_retake(original_prompt, new_prompt):
    st = state.load()
    for s in st["shots"]:
        if s["prompt"] == original_prompt:
            s["prompt"] = new_prompt
            s["retake_of"] = original_prompt
            s["status"] = "retake_submitted"
    state.save(st)
