"""`python -m agent.deliver` - send the farm's finished result back to the agent.

Finds the newest session holding a pending render_submit (adk web files your
chats under user "user"), waits until the farm says done, then delivers the
result by id - through the three lines in agent/drive.py answer().
"""
import json
import time

from world import broker

from . import config, drive, state
from .desk import render_desk

LEDGER = config.RUNS / "delivered.json"


def find_pending():
    """Newest (user, session, call) still waiting - thumbnail draft OR render."""
    async def _scan():
        service = drive.svc()
        found = []
        for user in ("user", config.USER):
            resp = await service.list_sessions(app_name=config.APP, user_id=user)
            for s in resp.sessions:
                for cid, name, r in await drive.pending(s.id, user_id=user):
                    if name in ("render_submit", "thumb_submit", "thumb_revise"):
                        found.append((s.last_update_time, user, s.id, cid, name, r))
        found.sort()
        return found[-1] if found else None
    return drive.run(_scan())


def main():
    hit = find_pending()
    if not hit:
        print("no pending render anywhere — type one in adk web first")
        return
    _, user, sid, cid, name, resp = hit
    print(f"  found it: session {sid} (user {user}) · {name} id={str(cid)[:12]}…")

    if name in ("thumb_submit", "thumb_revise"):
        from world import thumbstudio
        print("  waiting for the thumbnail studio (~20-30s)…")
        for _ in range(40):
            job = thumbstudio.poll(resp.get("job_id", ""))
            if job.get("status") == "done":
                out = drive.run(drive.answer(render_desk, sid, cid, name,
                                             {"status": "done", "kind": "thumb_draft",
                                              "url": job["url"]}, user_id=user))
                print("── result delivered (same id) → the run continued ──")
                print(f"  your draft: {job['url']}"
                      + ("" if job.get("generated") else "   (fallback image)"))
                print(f"  desk: {str(out)[:120]}")
                LEDGER.write_text(json.dumps({"user": user, "session": sid}))
                return
            time.sleep(2)
        print("draft still cooking — run deliver again")
        return

    print("  polling the farm until the job is done…")
    for _ in range(15):
        jobs = {j["id"]: j for j in broker.poll()}
        job = jobs.get(resp.get("job_id"))
        if job and job["status"] == "done":
            out = drive.run(drive.answer(render_desk, sid, cid, name,
                                         {"status": "done", "shot": resp["shot"],
                                          "url": job["url"]}, user_id=user))
            print("── result delivered (same id) → the run continued ──")
            print(f"  desk: {str(out)[:120]}")
            print("  now RELOAD that session in adk web — the result is a new event.")
            LEDGER.write_text(json.dumps({"user": user, "session": sid}))
            return
        time.sleep(1)
    print("farm still cooking — run deliver again")


if __name__ == "__main__":
    main()
