"""`python -m agent.finish` - deliver every remaining result, then publish:
machine results (renders done), the medic retake, the deadline stand-in, and
the human thumb approval (auto-approved here, loudly - Studio's button runs
this same module). When the join completes: gates, then publish."""
import time

from world import broker

from . import config, drive, joinlogic, state
from .desk import thumb_desk


def main():
    st = state.load()
    sid = joinlogic.desk_sid(st)
    t0 = time.time()

    for cid, name, resp in drive.run(drive.pending(f"{st['run_id']}_thumb")):
        print("── human approval: thumbnail — AUTO-APPROVED [workshop mode] ──")
        drive.run(drive.answer(thumb_desk, f"{st['run_id']}_thumb", cid, name,
                               {"status": "approved", "kind": "thumb"}))
        st = state.load()
        st["lineage"]["approvals"].append({"kind": "thumb", "at": time.time()})
        state.save(st)

    while time.time() - t0 < broker.deadline_s() + 25:
        st = state.load()
        jobs = {j["id"]: j for j in broker.poll()}

        for cid, name, resp in drive.run(drive.pending(sid)):
            job = jobs.get(resp.get("job_id"))
            if not job or joinlogic.already_answered(st, job["id"]):
                continue
            if job["status"] == "done":
                joinlogic.handle_done(cid, name, resp, job)
            elif job["status"] == "failed":
                joinlogic.handle_failed(cid, name, resp, job)
            st = state.load()

        waited = time.time() - state.load().get("render_started_at", t0)
        if waited > broker.deadline_s():   # a degraded farm is on the 2s clock, not Veo's 420s
            for cid, name, resp in drive.run(drive.pending(sid)):
                job = jobs.get(resp.get("job_id"))
                if job and job["status"] == "queued":
                    joinlogic.handle_deadline(cid, name, resp, job)

        if joinlogic.try_finish() is not None:
            return
        # Veo operations are polled, not hammered - but a degraded farm is a
        # local clock, so stop pacing for a model we are no longer calling.
        time.sleep(3.0 if config.REAL_VIDEO and not broker.degraded() else 1.0)

    # The window closed with results still out (a late retake, a slow farm).
    # A worker must never leave a lap hanging: every wait still open gets the
    # prebaked stand-in - the same deadline rule, applied one last time - and
    # the join is asked once more. Bounded by a clock, finished by a rule.
    jobs = {j["id"]: j for j in broker.poll()}
    for cid, name, resp in drive.run(drive.pending(sid)):
        job = jobs.get(resp.get("job_id")) or {"id": resp.get("job_id"), "status": "queued"}
        joinlogic.handle_deadline(cid, name, resp, job)
    if joinlogic.try_finish() is not None:
        return
    print("finish window elapsed; run `python -m agent.status` to inspect")


if __name__ == "__main__":
    main()
