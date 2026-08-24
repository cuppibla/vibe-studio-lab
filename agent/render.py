"""`python -m agent.render` - hand the script to the desk: N render submits in
ONE turn (machine waits), generate the real thumbnail, ring the human thumb
result delivery. Then everything is pending at once - see `python -m agent.status`."""
import json
import time

from world import thumbgen

from . import drive, state
from .desk import render_desk, thumb_desk


def main():
    st = state.load()
    if not st.get("script"):
        print("no script yet — finish the workflow first (agent.run)"); return
    run_id = st["run_id"]
    shots = [s["description"] for s in st["script"]["shots"]]

    print(f"── desk: submitting {len(shots)} shots in ONE turn ──")
    out = drive.run(drive.say(
        render_desk, f"{run_id}_desk",
        "Render these shots:\n" + json.dumps(shots, ensure_ascii=False)))
    print(f"  desk: {out!r}")
    st = state.load()
    st["shots"] = [{"prompt": s, "status": "submitted"} for s in shots]
    st["render_started_at"] = time.time()
    state.save(st)

    print("── thumbnail: generating from YOUR brief ──")
    thumb = thumbgen.generate(run_id, st["script"]["title"], st.get("choices", {}))
    state.update(thumb=thumb)
    print(f"  thumb: {thumb['ref']} · generated={thumb['generated']}")

    out = drive.run(drive.say(
        thumb_desk, f"{run_id}_thumb",
        f"Request approval for this thumbnail: {thumb['ref']}"))
    print(f"  thumb desk: {out!r}")
    print("⏸  3 machine waits + 1 human wait hang concurrently — and no process "
          "is alive. Deliver them: python -m agent.finish (or approve in Studio)")


if __name__ == "__main__":
    main()
