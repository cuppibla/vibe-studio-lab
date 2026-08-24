"""`python -m agent.approve` - deliver the human thumbnail approval, by hand.
(The Studio button answers the exact same pending call.)"""
import time

from . import drive, state
from .desk import thumb_desk


def main():
    st = state.load()
    sid = f"{st['run_id']}_thumb"
    pend = drive.run(drive.pending(sid))
    if not pend:
        print("no thumbnail waiting"); return
    for cid, name, resp in pend:
        print(f"approving thumbnail {resp.get('thumb_ref')}")
        drive.run(drive.answer(thumb_desk, sid, cid, name,
                               {"status": "approved", "kind": "thumb"}))
        st = state.load()
        st["lineage"]["approvals"].append({"kind": "thumb", "at": time.time()})
        state.save(st)


if __name__ == "__main__":
    main()
