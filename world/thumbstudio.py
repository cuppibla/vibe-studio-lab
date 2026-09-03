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


# ── the title band · a thumbnail is art PLUS words ─────────────────────────
# Image models garble long text, so the studio draws the art and then LAYS
# THE TITLE ON TOP itself - crisp every time, and the same house style.
FONTS = [
    "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",          # Cloud Shell
    "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",  # other Linux
    "/System/Library/Fonts/Supplemental/Arial Bold.ttf",             # macOS
    "/Library/Fonts/Arial Bold.ttf",
]


def _font(size: int):
    from PIL import ImageFont
    import pathlib as _p
    for f in FONTS:
        if _p.Path(f).exists():
            return ImageFont.truetype(f, size)
    return None                    # no font on this box: art without the band


def title_band(png, title: str) -> None:
    """Draw the video's title across the bottom of the thumbnail, in place."""
    if not title:
        return
    try:
        from PIL import Image, ImageDraw
        img = Image.open(png).convert("RGB")
        W, H = img.size
        font = _font(max(28, int(W * 0.052)))
        if font is None:
            return
        draw = ImageDraw.Draw(img, "RGBA")
        # wrap to at most two lines that fit the width
        words, lines, line = title.upper().split(), [], ""
        for w in words:
            trial = f"{line} {w}".strip()
            if draw.textlength(trial, font=font) <= W * 0.86 or not line:
                line = trial
            else:
                lines.append(line); line = w
            if len(lines) == 2:
                break
        if line and len(lines) < 2:
            lines.append(line)
        lh = font.size * 1.22
        band_h = int(lh * len(lines) + font.size * 0.9)
        draw.rectangle([0, H - band_h, W, H], fill=(43, 35, 32, 214))
        y = H - band_h + font.size * 0.42
        for ln in lines:
            x = (W - draw.textlength(ln, font=font)) / 2
            draw.text((x, y), ln, font=font, fill=(255, 250, 244))
            y += lh
        img.save(png)
    except Exception as e:                     # never fail a lap over a font
        print(f"  [thumbstudio] title band skipped ({str(e)[:60]})")


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
    # the CLEAN master, never the banded display copy - otherwise turn 2 would
    # ask the model to reproduce burnt-in text
    parent_png = DRAFTS / f"{parent.get('id')}.png" if parent.get("id") else None
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
    shown = out                    # what the app displays
    if ok:                         # keep `out` clean; band a COPY for display
        import shutil as _sh
        shown = DRAFTS / f"{job_id}_titled.png"
        _sh.copyfile(out, shown)
        title_band(shown, anchor(_load()["jobs"][job_id]))
    d = _load()                    # re-read: the ledger may have moved on
    d["jobs"][job_id].update({"status": "done", "generated": ok,
                              "url": f"{WEB}/{shown.name}" if ok else FALLBACK,
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
        title_band(out, title)          # art, then the words on top
        return {"ref": f"/static/thumbs/{out.name}", "generated": True}
    except Exception as e:
        print(f"  [thumbstudio] fell back to prebaked ({str(e)[:70]})")
        shutil.copyfile(config.ROOT / "app" / FALLBACK.lstrip("/"), out)
        title_band(out, title)
        return {"ref": f"/static/thumbs/{out.name}", "generated": False}


if __name__ == "__main__":
    work(sys.argv[sys.argv.index("--job") + 1])
