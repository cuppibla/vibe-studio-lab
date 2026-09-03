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

A thumbnail is art PLUS words. Image models garble text, so the words are
code's job: caption_sticker() prints a 2-4 word caption (written by the
agent, not the user) in the corner of the finished art.

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
    "A YouTube thumbnail illustration in a WIDE 16:9 frame that the scene fills "
    "edge to edge - no borders, no side bars, no letterboxing, no vignette, no "
    "picture frame. One comic decisive moment, expressive, joyful disaster "
    "energy, the subject large and centered-right, the lower-left corner calm "
    "and uncluttered (a caption sticker goes there). No text, no words, no "
    "letters, no logos.")
FILL_THE_FRAME = (" IMPORTANT: the artwork must cover the whole wide canvas - "
                  "paint all the way to the left and right edges, never leave "
                  "empty bars.")


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


def submit(description: str, parent: str | None = None, caption: str = "") -> str:
    """Queue a draft thumbnail and start the worker. Returns instantly.
    `caption` is the 2-4 word sticker text; a revision inherits its parent's."""
    job_id = f"thm_{uuid.uuid4().hex[:6]}"
    d = _load()
    d["jobs"][job_id] = {"id": job_id, "description": description, "parent": parent,
                         "caption": caption.strip(), "status": "queued",
                         "submitted_at": time.time()}
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


def _chain(job: dict):
    """Walk the parent chain back to turn 1."""
    jobs = _load()["jobs"]
    seen = set()
    while True:
        yield job
        if not job.get("parent") or job["parent"] not in jobs or job["id"] in seen:
            return
        seen.add(job["id"])
        job = jobs[job["parent"]]


def anchor(job: dict) -> str:
    """The idea the user actually typed - turn 1's description. Turn 2's
    description is a change ('warmer light'), not a scene, so the lineage in
    the ledger is what answers 'what is this?'."""
    return list(_chain(job))[-1].get("description", "")


def short(text: str, n: int = 4) -> str:
    """A caption when nobody wrote one: the first few words."""
    return " ".join(text.replace("—", " ").split()[:n])


def caption_for(job: dict) -> str:
    """The sticker text: the first caption found up the chain, else a short
    cut of the original idea."""
    for j in _chain(job):
        if j.get("caption"):
            return j["caption"]
    return short(anchor(job))


# ── the caption sticker · a thumbnail is art PLUS words ────────────────────
# Image models garble long text, so the studio draws the art and then prints
# the caption itself - a chunky rounded display face (Lilita One, bundled,
# OFL) with a dark outline, tilted like a sticker, in the calm corner the
# prompt reserved for it.
FONTS = [
    str(config.ROOT / "app" / "static" / "fonts" / "LilitaOne-Regular.ttf"),   # bundled
    "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",                     # any Linux
    "/System/Library/Fonts/Supplemental/Arial Rounded Bold.ttf",                # macOS
]
INK = (43, 35, 32)
PAPER = (255, 250, 244)


def _font(size: int):
    from PIL import ImageFont
    import pathlib as _p
    for f in FONTS:
        if _p.Path(f).exists():
            return ImageFont.truetype(f, size)
    return None                    # no font on this box: art without the caption


def _wrap(words, font, draw, max_w):
    lines, line = [], ""
    for w in words:
        trial = f"{line} {w}".strip()
        if draw.textlength(trial, font=font) <= max_w or not line:
            line = trial
        else:
            lines.append(line)
            line = w
    if line:
        lines.append(line)
    return lines


def caption_sticker(png, text: str) -> None:
    """Print the caption on the thumbnail, in place: white letters, dark
    outline, a soft shadow, a 3-degree tilt, bottom-left. Never fails a lap."""
    if not text:
        return
    try:
        from PIL import Image, ImageDraw
        img = Image.open(png).convert("RGBA")
        W, H = img.size
        words = text.strip().split()
        probe = ImageDraw.Draw(img)
        size = int(H * 0.17)
        while size > int(H * 0.08):           # shrink until it fits in two lines
            font = _font(size)
            if font is None:
                return
            lines = _wrap(words, font, probe, W * 0.62)
            if len(lines) <= 2:
                break
            size -= 2
        stroke = max(3, int(size * 0.10))
        lh = size * 1.02
        x0, y0 = int(W * 0.05), int(H - H * 0.075 - lh * len(lines))
        layer = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        d = ImageDraw.Draw(layer)
        for i, ln in enumerate(lines):
            y = y0 + i * lh
            d.text((x0 + size * 0.05, y + size * 0.07), ln, font=font,      # shadow
                   fill=(*INK, 110), stroke_width=stroke, stroke_fill=(*INK, 110))
            d.text((x0, y), ln, font=font, fill=(*PAPER, 255),             # letters
                   stroke_width=stroke, stroke_fill=(*INK, 255))
        layer = layer.rotate(3, resample=Image.BICUBIC,
                             center=(x0, y0 + lh * len(lines)))            # sticker tilt
        img.alpha_composite(layer)
        img.convert("RGB").save(png)
    except Exception as e:                     # never fail a lap over a font
        print(f"  [thumbstudio] caption skipped ({str(e)[:60]})")


# ── the frame guard · a wide canvas must be a wide picture ─────────────────
def _letterboxed(img) -> bool:
    """True when the model painted a narrow picture and padded the sides."""
    from PIL import ImageStat
    W, H = img.size
    band = max(8, int(W * 0.10))
    g = img.convert("L")
    left = ImageStat.Stat(g.crop((0, 0, band, H)))
    right = ImageStat.Stat(g.crop((W - band, 0, W, H)))
    return left.stddev[0] < 7 and right.stddev[0] < 7 and \
        abs(left.mean[0] - right.mean[0]) < 14


def _cover_crop(img):
    """Last resort: cut the padded bars away and re-fill the wide frame."""
    from PIL import Image, ImageStat
    W, H = img.size
    g = img.convert("L").resize((240, 60))
    cols = [ImageStat.Stat(g.crop((x, 0, x + 1, 60))).stddev[0] for x in range(240)]
    live = [x for x, s in enumerate(cols) if s > 8]
    if not live:
        return img
    x0, x1 = int(live[0] / 240 * W), int((live[-1] + 1) / 240 * W)
    content = img.crop((x0, 0, x1, H))
    scale = W / content.width
    grown = content.resize((W, int(H * scale)), Image.LANCZOS)
    top = (grown.height - H) // 2
    return grown.crop((0, top, W, top + H))


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


def _call(client, contents, out) -> bool:
    return _extract(client.models.generate_content(model=MODEL, contents=contents,
                                                   config=_cfg()), out)


def _wide(client, contents, out, retry_with=None) -> bool:
    """Generate, then guard the frame: a letterboxed result is drawn once more
    with the fill-the-frame line; if it still comes back padded, cover-crop."""
    from PIL import Image
    if not _call(client, contents, out):
        return False
    if _letterboxed(Image.open(out)):
        print("  [thumbstudio] letterboxed - asking for a full-width frame once more")
        if retry_with is not None and _call(client, retry_with, out) \
                and not _letterboxed(Image.open(out)):
            return True
        _cover_crop(Image.open(out).convert("RGB")).save(out)
    return True


def _generate(job: dict, out) -> bool:
    from google.genai import types as gt
    client = _client()            # keep the reference: a temporary gets closed mid-call
    parent = _load()["jobs"].get(job.get("parent") or "", {})
    # the CLEAN master, never the stickered display copy - otherwise turn 2 would
    # ask the model to reproduce burnt-in text
    parent_png = DRAFTS / f"{parent.get('id')}.png" if parent.get("id") else None
    if parent_png and parent_png.exists():
        # TURN 2 - the previous image IS the context; no re-describing the scene
        contents = [gt.Part.from_bytes(data=parent_png.read_bytes(),
                                       mime_type="image/png"),
                    change_prompt(job["description"])]
        return _wide(client, contents, out)
    prompt = draft_prompt(job["description"])
    return _wide(client, prompt, out, retry_with=prompt + FILL_THE_FRAME)


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
    if ok:                         # keep `out` clean; sticker a COPY for display
        import shutil as _sh
        shown = DRAFTS / f"{job_id}_titled.png"
        _sh.copyfile(out, shown)
        caption_sticker(shown, caption_for(_load()["jobs"][job_id]))
    d = _load()                    # re-read: the ledger may have moved on
    d["jobs"][job_id].update({"status": "done", "generated": ok,
                              "url": f"{WEB}/{shown.name}" if ok else FALLBACK,
                              "finished_at": time.time(),
                              **({"error": err} if err else {})})
    _save(d)


def generate(run_id: str, title: str, direction: str, attempt: int = 0,
             hook: str = "") -> dict:
    """The LAP's synchronous path: the video's real thumbnail, from your
    chosen direction. Same prompt layers as the drafts; the sticker text is
    the direction's `hook` (2-4 words the proposer wrote). Falls back to a
    prebaked thumb (honestly flagged) if the image model is unavailable."""
    import shutil
    THUMBS.mkdir(parents=True, exist_ok=True)
    suffix = f"_r{attempt}" if attempt else ""
    out = THUMBS / f"{run_id}{suffix}.png"
    words = hook.strip() or short(title, 5)
    try:
        client = _client()   # keep the reference: a temporary gets closed mid-call
        prompt = draft_prompt(direction or title)
        if not _wide(client, prompt, out, retry_with=prompt + FILL_THE_FRAME):
            raise RuntimeError("no image part in response")
        caption_sticker(out, words)          # art, then the words on top
        return {"ref": f"/static/thumbs/{out.name}", "generated": True}
    except Exception as e:
        print(f"  [thumbstudio] fell back to prebaked ({str(e)[:70]})")
        shutil.copyfile(config.ROOT / "app" / FALLBACK.lstrip("/"), out)
        caption_sticker(out, words)
        return {"ref": f"/static/thumbs/{out.name}", "generated": False}


if __name__ == "__main__":
    work(sys.argv[sys.argv.index("--job") + 1])
