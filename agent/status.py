"""`python -m agent.status` - every open call across the lap's sessions.
No process is running; these are rows."""
from . import drive, state


def main():
    st = state.load()
    if not st.get("run_id"):
        print("no lap yet — python -m agent.run"); return
    total = 0
    for suffix, label in (("_wf", "the workflow (human doors)"),
                          ("_desk", "the render desk (machine)"),
                          ("_thumb", "the thumb desk (human)")):
        sid = f"{st['run_id']}{suffix}"
        for cid, name, resp in drive.run(drive.pending(sid)):
            kind = resp.get("kind") or resp.get("job_id") or ""
            print(f"  ⏸  {label:34} {name}(id={str(cid)[:10]}…)  {kind}")
            total += 1
    print(f"\n  {total} call(s) waiting — no thread, no process. "
          "Answering one = a new response with the same id.")


if __name__ == "__main__":
    main()
