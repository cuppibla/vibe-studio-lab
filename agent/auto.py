"""The app's automation - the chains behind Vibe Studio's three buttons.

  python -m agent.auto direction --pick 1 [--custom "…"]
      answer the form, and if the policy gate cleared it, roll straight
      into rendering. (BLOCK ends the lap politely - nothing to chain.)

  python -m agent.auto ship
      approve the thumbnail, then finish: deliver every render, run the
      publish backstop, put the video on the wall (and the room, silently).

  python -m agent.auto rethumb
      reject the current thumbnail, generate a fresh one from the SAME
      direction, and ask for approval again.

Chains live HERE, not in the graph: they cross the world (renders, publish),
and the graph never waits for the world.
"""
import json
import os
import sys
import time

from . import answer as answer_cli
from . import approve as approve_cli
from . import drive, finish as finish_cli, lap, render as render_cli, state
from .desk import thumb_desk


def direction(argv):
    if not answer_cli.main(argv):
        return
    if lap.where()["phase"] == "scripted":
        render_cli.main()
    # phase "blocked": the polite stop - the card explains, nothing to chain


def _wait_for_thumb(timeout_s: int = 180) -> bool:
    """Approve can be pressed while the render chain is still generating the
    thumbnail. The precondition for answering is that thumb_desk has actually
    rung - i.e. a pending approval call exists. Wait for THAT, not for a pid:
    a signal, not a race."""
    st = state.load()
    sid = f"{st.get('run_id')}_thumb"
    for _ in range(timeout_s):
        if drive.run(drive.pending(sid)):
            return True
        time.sleep(1)
    return False


def ship():
    if state.load().get("published"):
        print("already published — nothing to ship")
        return
    if not _wait_for_thumb():
        print("no thumbnail to approve — is a lap running?")
        return
    approve_cli.main()
    finish_cli.main()


def rethumb():
    _wait_for_thumb()
    from world import thumbstudio
    st = state.load()
    run_id = st.get("run_id")
    if not run_id or not st.get("thumb"):
        print("no thumbnail on review — nothing to regenerate"); return
    sid = f"{run_id}_thumb"
    for cid, name, resp in drive.run(drive.pending(sid)):
        drive.run(drive.answer(thumb_desk, sid, cid, name,
                               {"status": "rejected", "kind": "thumb"}))
        print("── thumbnail rejected — drawing another from the same direction ──")
    attempt = int(st.get("thumb_attempt", 0)) + 1
    thumb = thumbstudio.generate(run_id, st["script"]["title"],
                                 st.get("direction", ""), attempt=attempt)
    state.update(thumb=thumb, thumb_attempt=attempt)
    out = drive.run(drive.say(
        thumb_desk, sid, f"Request approval for this thumbnail: {thumb['ref']}"))
    print(f"  new thumb: {thumb['ref']} · desk: {out!r}")


def main():
    cmd = sys.argv[1] if len(sys.argv) > 1 else ""
    if cmd == "direction":
        direction(sys.argv[2:])
    elif cmd == "ship":
        ship()
    elif cmd == "rethumb":
        rethumb()
    else:
        print("usage: python -m agent.auto direction|ship|rethumb [...]")


if __name__ == "__main__":
    main()
