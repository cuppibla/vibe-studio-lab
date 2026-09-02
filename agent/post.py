"""Post-production workflow (pure compute + dict-edge gates).
editor -> policy_check(OK/BLOCK) -> eval_gate(PASS/FAIL) -> publisher.
Gates are checker EVALS - and they run BEFORE the side effect."""
import pathlib
import time

from google.adk import Event, Runner, Workflow
from google.adk.workflow import START
from google.genai import types as gtypes

from . import config, drive, state

# Policy is DATA, not code: the words live in policy_words.txt beside this
# file, and policy_check reads them at DECISION time - edit the file, and
# the very next run enforces it. No restart, no redeploy.
POLICY_FILE = pathlib.Path(__file__).parent / "policy_words.txt"


def policy_words() -> list[str]:
    return [w.strip().lower() for w in POLICY_FILE.read_text().splitlines()
            if w.strip() and not w.strip().startswith("#")]


def editor(node_input):
    """Cut the shots together. The farm's clips are prebaked receipts, so the
    real playable artifact is built from the thumbnail the studio generated
    from YOUR brief - that is what plays on the Channel wall."""
    from world import renderfarm
    st = state.load()
    urls = [s.get("url") for s in st["shots"] if s.get("url")]
    final_ref = renderfarm.final_cut(st["run_id"], (st.get("thumb") or {}).get("ref", ""))
    if not final_ref:                       # no ffmpeg: an honest manifest, not a fake .mp4
        final_ref = f"runs/final_{st['run_id']}.txt"
        (config.ROOT / final_ref).write_text("PREBAKED CUT\n" + "\n".join(urls))
    return Event(output={"final_ref": final_ref, "n_shots": len(urls)})


def policy_check(node_input):
    st = state.load()
    text = (st["script"]["title"] + " " + st["script"]["description"]).lower()
    bad = [w for w in policy_words() if w in text]
    st["lineage"]["gates"]["policy"] = {"ok": not bad, "hits": bad}
    state.save(st)
    return Event(output=node_input, route="BLOCK" if bad else "OK")


def eval_gate(node_input):
    """Deterministic conduct checks - a checker eval needs no golden answer."""
    st = state.load()
    s, lin = st["script"], st["lineage"]
    valid_sources = {"trends", "backcatalog"}
    valid_sources |= {f"memory#{m['ref']}" for m in st.get("memory_facts", [])
                      if m.get("ref")}
    valid_sources |= {f"graph#{q}" for q in st.get("graph_query_ids", [])}
    invented = [e for e in lin["evidence"] if e["source"] not in valid_sources]
    checks = {
        "title_len_ok": len(s["title"]) <= 60,
        "has_tags": len(s.get("tags", [])) >= 2,
        "no_invented_evidence": not invented,
    }
    lin["gates"]["eval"] = {"checks": checks, "invented": invented}
    state.save(st)
    return Event(output=node_input, route="PASS" if all(checks.values()) else "FAIL")


def quarantine(node_input):
    return Event(output={"published": False, "why": "policy BLOCK"})


def rejected(node_input):
    return Event(output={"published": False, "why": "eval FAIL"})


def publisher(node_input):
    """Publish IS a tool call - and the gates just ran BEFORE it."""
    from world import platform
    st = state.load()
    res = platform.publish(
        st["creds"], st["run_id"],
        title=st["script"]["title"], description=st["script"]["description"],
        duration_ms=st["duration_ms"], lap=st["lap"],
        video_ref=node_input["final_ref"],
        thumb_ref=(st.get("thumb") or {}).get("ref", ""),
        lineage=st["lineage"])
    st["published"] = {**res, "at": time.time()}
    state.save(st)
    return Event(output={"published": True, **res})


wf_post = Workflow(
    name="post", description="editor -> gates -> publisher",
    edges=[(START, editor, policy_check),
           (policy_check, {"OK": eval_gate, "BLOCK": quarantine}),
           (eval_gate, {"PASS": publisher, "FAIL": rejected})])


async def run_post(run_id: str) -> dict:
    runner = Runner(node=wf_post, app_name=config.APP,
                    session_service=drive.svc(), auto_create_session=True)
    final = None
    async for ev in runner.run_async(
            user_id=config.USER, session_id=f"{run_id}_post",
            new_message=gtypes.Content(role="user", parts=[gtypes.Part(text="ship it")])):
        out = getattr(ev, "output", None)
        if isinstance(out, dict) and "published" in out:
            final = out
    if final is None:
        raise RuntimeError("post workflow produced no result")
    return final
