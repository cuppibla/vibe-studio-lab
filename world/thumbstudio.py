"""The thumbnail studio - real long-running work, and a consistent look.

Two ideas live here, and the codelab teaches both:

1 · LONG RUNNING.  submit() starts a detached worker and returns a receipt
    immediately. The image model takes 20-30 seconds; nothing in the agent's
    process waits for it.

2 · A CONSISTENT LOOK, AND A SECOND TURN.  The prompt is built in layers so
    the studio's style never depends on what a student types:

      ANCHOR      the idea the user gave       <- the ONLY layer user text touches
      STYLE-LOCK  the studio's house style     <- fixed, every time
      CONSTRAINTS framing / no-text / output   <- fixed, every time

    Turn 2 (revise) does NOT re-describe the scene: it sends the PNG turn 1
    produced back to the model with a change request. The in-memory chat
    session died with turn 1's worker - the file and the ledger row are what
    survived, and they are enough. That is state management for long-running
    work, in one function.

The same prompt layers also serve the LAP: generate() is the synchronous
path that turns your chosen direction into the video's real thumbnail.

Worker entry:  python -m world.thumbstudio --job <job_id>
"""
import json
import subprocess
import sys
import time
import uuid

from agent import config

DRAFTS = config.ROOT / "app" / "static" / "thumbs" / "drafts"
THUMBS = config.ROOT / "app" / "static" / "thumbs"
LEDGER = config.RUNS / "thumbdrafts.json"
WEB = "/static/thumbs/drafts"
FALLBACK = "/static/art/thumb-chores.png"
MODEL = "gemini-3-pro-image"

STYLE_LOCK = (
    "Cozy low-poly faceted 3D art, Monument Valley register, warm pastel "
    "palette of cream, terracotta, sage green and sky blue, soft bright "
    "daylight, handmade miniature diorama feel.")
CONSTRAINTS = (
    "YouTube thumbnail illustration, 16:9 framing, one comic decisive moment, "
    "expressive, joyful disaster energy, generous negative space, no text, "
    "no words, no letters, no logos.")


def draft_prompt(idea: str) -> str:
    """ANCHOR + STYLE-LOCK + CONSTRAINTS. User words slot in as DATA."""
    return f"A video thumbnail. The scene is: {idea}. {STYLE_LOCK} {CONSTRAINTS}"


def change_prompt(change: str) -> str:
    """Turn 2: the same scene, one thing changed. Consistency demanded loudly."""
    return (f"Edit this exact thumbnail: {change}. Keep the SAME scene, SAME "
            f"characters, SAME colors and SAME composition - change nothing "
            f"else. {STYLE_LOCK} {CONSTRAINTS}")


def _load() -> dict:
    return json.loads(LEDGER.read_text()) if LEDGER.exists() else {"jobs": {}}


def _save(d: dict) -> None:
    config.RUNS.mkdir(exist_ok=True)
    LEDGER.write_text(json.dumps(d, indent=2))


def submit(description: str, parent: str | None = None) -> str:
    """Queue a draft thumbnail and start the worker. Returns instantly."""
    job_id = f"thm_{uuid.uuid4().hex[:6]}"
    d = _load()
    d["jobs"][job_id] = {"id": job_id, "description": description, "parent": parent,
                         "status": "queued", "submitted_at": time.time()}
    _save(d)
    subprocess.Popen([sys.executable, "-m", "world.thumbstudio", "--job", job_id],
                     cwd=str(config.ROOT), stdout=subprocess.DEVNULL,
                     stderr=subprocess.DEVNULL, start_new_session=True)
    return job_id


def poll(job_id: str) -> dict:
    return _load()["jobs"].get(job_id, {"status": "unknown", "id": job_id})


def latest() -> dict | None:
    """The newest finished draft - what the dev-UI chapters point at."""
    done = [j for j in _load()["jobs"].values() if j.get("status") == "done"]
    return max(done, key=lambda j: j.get("finished_at", 0)) if done else None


def anchor(job: dict) -> str:
    """Walk the parent chain back to turn 1 - the idea the user actually
    typed. Turn 2's description is a change ('warmer light'), not a scene,
    so the lineage in the ledger is what answers 'what is this?'."""
    jobs = _load()["jobs"]
    seen = set()
    while job.get("parent") and job["parent"] in jobs and job["id"] not in seen:
        seen.add(job["id"])
        job = jobs[job["parent"]]
    return job.get("description", "")


def _client():
    from google import genai
    return genai.Client()          # env decides: Vertex via ADC, or an AI Studio key


def _extract(response, out) -> bool:
    for part in response.candidates[0].content.parts:
        data = getattr(getattr(part, "inline_data", None), "data", None)
        if data:
            out.write_bytes(data)
            return True
    return False


def _cfg():
    from google.genai import types as gt
    return gt.GenerateContentConfig(response_modalities=["TEXT", "IMAGE"],
                                    image_config=gt.ImageConfig(aspect_ratio="16:9"))


def _generate(job: dict, out) -> bool:
    from google.genai import types as gt
    client = _client()            # keep the reference: a temporary gets closed mid-call
    parent = _load()["jobs"].get(job.get("parent") or "", {})
    parent_png = (config.ROOT / "app" / parent.get("url", "").lstrip("/")
                  if parent.get("url", "").startswith(WEB) else None)
    if parent_png and parent_png.exists():
        # TURN 2 - the previous image IS the context; no re-describing the scene
        contents = [gt.Part.from_bytes(data=parent_png.read_bytes(),
                                       mime_type="image/png"),
                    change_prompt(job["description"])]
    else:
        contents = draft_prompt(job["description"])
    return _extract(client.models.generate_content(model=MODEL, contents=contents,
                                                   config=_cfg()), out)


def work(job_id: str) -> None:
    d = _load()
    job = d["jobs"].get(job_id)
    if not job:
        return
    DRAFTS.mkdir(parents=True, exist_ok=True)
    out = DRAFTS / f"{job_id}.png"
    job["status"] = "working"
    _save(d)
    err = None
    try:
        ok = _generate(job, out)
    except Exception as e:
        ok, err = False, str(e)[:140]
    d = _load()                    # re-read: the ledger may have moved on
    d["jobs"][job_id].update({"status": "done", "generated": ok,
                              "url": f"{WEB}/{out.name}" if ok else FALLBACK,
                              "finished_at": time.time(),
                              **({"error": err} if err else {})})
    _save(d)


def generate(run_id: str, title: str, direction: str, attempt: int = 0) -> dict:
    """The LAP's synchronous path: the video's real thumbnail, from your
    chosen direction. Same prompt layers as the drafts. Falls back to a
    prebaked thumb (honestly flagged) if the image model is unavailable."""
    import shutil
    THUMBS.mkdir(parents=True, exist_ok=True)
    suffix = f"_r{attempt}" if attempt else ""
    out = THUMBS / f"{run_id}{suffix}.png"
    try:
        client = _client()   # keep the reference: a temporary gets closed mid-call
        ok = _extract(client.models.generate_content(
            model=MODEL, contents=draft_prompt(direction or title), config=_cfg()), out)
        if not ok:
            raise RuntimeError("no image part in response")
        return {"ref": f"/static/thumbs/{out.name}", "generated": True}
    except Exception as e:
        print(f"  [thumbstudio] fell back to prebaked ({str(e)[:70]})")
        shutil.copyfile(config.ROOT / "app" / FALLBACK.lstrip("/"), out)
        return {"ref": f"/static/thumbs/{out.name}", "generated": False}


if __name__ == "__main__":
    work(sys.argv[sys.argv.index("--job") + 1])
