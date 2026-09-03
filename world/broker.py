"""The render farm - REAL by default (Veo 3.1), with a prebaked clock as the
fallback. File-backed, survives process boundaries.

REAL (STUDIO_REAL_VIDEO=1, the default): submit() starts ONE Veo long-running
operation per shot and returns a receipt at once; poll() asks the operation
whether it is done and, when it is, downloads the mp4 into app/static/renders.
A shot takes a minute or three. This is the same shape as the thumbnail
studio, at the scale of a real production: the agent's turn ended long ago,
the operation lives on Google's side, the receipt lives in the session.

PREBAKED (STUDIO_REAL_VIDEO=0, or Veo unreachable): a deterministic clock so
the lab still runs with no video model and no cost -
  job 0 -> done after 2s · job 1 -> FAILS once (the medic's cue) ·
  job 2 -> never completes (the deadline's cue) · job 3+ -> done after 2s

FAILOVER: a Veo call gets exactly ONE retry. If the retry fails too, the whole
RUN degrades to that prebaked clock (see _degrade) and says so loudly - in the
worker log and on the page - because a learner must never mistake a stand-in
for Veo output. The degraded flag lives in broker.json, so it survives the
process boundary and a resumed run picks it back up instead of re-dialling a
model that is not answering.

Pull-through advancement: state only moves when poll() is called - no daemon.
"""
import json
import os
import time

from agent import config

# the same model wears two names: `-preview` on AI Studio, `-001` on Vertex
VEO_MODEL = os.environ.get("STUDIO_VEO_MODEL") or (
    "veo-3.1-fast-generate-001" if config.VERTEX else "veo-3.1-fast-generate-preview")
RENDERS = config.ROOT / "app" / "static" / "renders"
WEB = "/static/renders"
# the same house style the thumbnail studio locks, spoken to a video model
STYLE = ("Cozy low-poly faceted 3D animation, Monument Valley register, warm "
         "pastel palette of cream, terracotta, sage green and sky blue, soft "
         "bright daylight, handmade miniature diorama feel, one gentle camera "
         "move. No text, no captions, no subtitles, no logos.")

_client_ref = None


VEO_LOCATION = os.environ.get("STUDIO_VEO_LOCATION", "us-central1")


def _client():
    """Vertex via ADC (Cloud Shell) or an AI Studio key - like the rest of the
    lab, except that Veo is served from a REGION, not the `global` endpoint
    Gemini uses, so the Vertex client here pins one."""
    global _client_ref
    if _client_ref is None:
        from google import genai
        if config.VERTEX:
            _client_ref = genai.Client(vertexai=True, project=os.environ.get("GOOGLE_CLOUD_PROJECT"),
                                       location=VEO_LOCATION)
        else:
            _client_ref = genai.Client()
    return _client_ref


def _reset_client() -> None:
    """Drop the cached client so the one retry gets a fresh one - a client built
    against a half-configured environment stays broken otherwise."""
    global _client_ref
    _client_ref = None


# The API saying no: it will say no again in three minutes, so there is nothing
# to wait for. Anything else (a socket hiccup, a 503) still gets its one retry.
_FATAL = ("permission", "denied", "quota", "exceeded", "not found", "unauthorized",
          "unauthenticated", "invalid argument", "invalid_argument", "billing",
          "api key", "api_key", "403", "404", "429")


def _fatal_api_error(e: BaseException) -> bool:
    code = getattr(e, "code", None) or getattr(e, "status_code", None)
    if code in (400, 401, 403, 404, 429):
        return True
    blob = f"{type(e).__name__} {e}".lower()
    return any(k in blob for k in _FATAL)


def _load() -> dict:
    if config.BROKER.exists():
        return json.loads(config.BROKER.read_text())
    return {"jobs": []}


def _save(d) -> None:
    config.BROKER.write_text(json.dumps(d, indent=2))


def degraded() -> dict | None:
    """Has this run failed over to the prebaked clock? Read by the deadline and
    by Studio's page - the one source of truth, on disk, shared by every worker."""
    return _load().get("degraded")


def deadline_s() -> float:
    """How long to wait on the farm. A degraded run is on the 2-second clock,
    so holding it to Veo's 420s window would spend the outage twice."""
    return config.PREBAKED_DEADLINE_S if degraded() else config.DEADLINE_S


def _degrade(d: dict, reason: str) -> None:
    """Fail this RUN over to the prebaked clock - once, loudly, and for good.

    Every real job still queued becomes a prebaked one on the spot: leaving them
    to poll an operation that will never answer is exactly the hang we are here
    to remove. Idempotent, so a resumed run re-reads the flag and moves on."""
    if d.get("degraded"):
        return
    d["degraded"] = {"reason": reason, "at": time.time()}
    print(f"  [farm] !! VEO UNAVAILABLE - {reason}")
    print("  [farm] !! this run is DEGRADED to the prebaked clock: the clips below "
          "are STAND-INS, not Veo output")
    for j in d["jobs"]:
        if j.get("real") and j["status"] == "queued":
            j["real"] = False
            j["submitted_at"] = time.time()          # the prebaked clock starts now
            j["note"] = f"degraded to prebaked - {reason}"


def _submit_real(job: dict, prompt: str) -> str | None:
    """Start ONE Veo operation. Real, then exactly one retry, then say why.

    Returns None on success, or the reason the run should degrade. This is the
    submission, not the render: two attempts cost seconds, so a 403 surfaces as
    a 403 in seconds instead of anywhere near the render deadline."""
    from google.genai import types as gt
    last, fatal = "", False
    for attempt in (1, 2):
        try:
            op = _client().models.generate_videos(
                model=VEO_MODEL, prompt=f"{prompt} {STYLE}",
                config=gt.GenerateVideosConfig(
                    aspect_ratio="16:9", resolution="720p", number_of_videos=1,
                    negative_prompt="text, subtitles, captions, watermark, logo"))
            job.update(real=True, op=op.name, model=VEO_MODEL)
            if attempt == 2:
                print(f"  [farm] veo submit recovered on the retry ({job['id']})")
            return None
        except Exception as e:
            last, fatal = f"{type(e).__name__}: {str(e)[:110]}", _fatal_api_error(e)
            print(f"  [farm] veo submit attempt {attempt}/2 failed: {last}")
            _reset_client()      # a client built against a bad env stays bad
    return (f"veo refused the submission ({last})" if fatal
            else f"veo submit failed twice ({last})")


def submit(prompt: str) -> str:
    """One shot -> one receipt. Real mode starts the Veo operation right here
    (a two-second call) and stores its NAME - that string is all a later
    process needs to find the work again."""
    d = _load()
    idx = len(d["jobs"])
    job = {"id": f"job_{idx}", "idx": idx, "prompt": prompt, "status": "queued",
           "submitted_at": time.time(), "failed_before": False, "real": False}
    if d.get("degraded"):                      # already failed over: don't re-dial
        job["note"] = f"prebaked stand-in - {d['degraded']['reason']}"
    elif config.REAL_VIDEO:
        why = _submit_real(job, prompt)
        if why:
            _degrade(d, why)
            job["note"] = f"prebaked stand-in - {why}"
    d["jobs"].append(job)
    _save(d)
    return job["id"]


def _advance_real(j: dict) -> None:
    """Ask the operation; when done, pull the bytes down next to the app."""
    from google.genai import types as gt
    op = _client().operations.get(gt.GenerateVideosOperation(name=j["op"]))
    if not op.done:
        return
    err = getattr(op, "error", None)
    resp = getattr(op, "response", None) or getattr(op, "result", None)
    vids = (getattr(resp, "generated_videos", None) or []) if resp else []
    if err or not vids:
        j["status"] = "failed"
        j["failed_before"] = True
        j["reason"] = (str(err)[:140] if err else
                       "the model returned no video (filtered or empty result)")
        return
    RENDERS.mkdir(parents=True, exist_ok=True)
    out = RENDERS / f"veo_{j['id']}_{int(j['submitted_at'])}.mp4"
    video = vids[0].video
    data = getattr(video, "video_bytes", None)          # Vertex hands the bytes back inline
    if not data:
        try:
            data = _client().files.download(file=video)   # the AI Studio path: a Files-API download
        except Exception as e:
            data = None
            j["download_error"] = str(e)[:100]
    if not data and getattr(video, "uri", ""):          # a GCS uri (output_gcs_uri was set)
        j["status"], j["reason"], j["failed_before"] = "failed", f"video landed in GCS ({video.uri}) - not fetched", True
        return
    if not data:
        j["status"], j["reason"], j["failed_before"] = "failed", "download returned nothing", True
        return
    out.write_bytes(data)
    j["status"], j["url"], j["finished_at"] = "done", f"{WEB}/{out.name}", time.time()


def poll() -> list[dict]:
    """Advance and return all jobs - real ones by asking Veo, prebaked ones by
    the clock table above."""
    d = _load()
    now = time.time()
    for j in d["jobs"]:
        if j["status"] != "queued":
            continue
        if j.get("real"):
            try:
                _advance_real(j)
            except Exception as e:
                # A slow operation answers `done: false` - it does NOT raise. So
                # this is an error, not patience: tolerate one, then fail over
                # rather than re-asking a dead endpoint until the deadline.
                j["op_errors"] = j.get("op_errors", 0) + 1
                why = f"{type(e).__name__}: {str(e)[:110]}"
                print(f"  [farm] veo poll attempt {j['op_errors']}/2 on {j['id']} failed: {why}")
                if _fatal_api_error(e) or j["op_errors"] >= 2:
                    _degrade(d, f"veo polling failed ({why})")
            if j.get("real"):
                continue                       # still Veo's; the clock below is not ours
        age = now - j["submitted_at"]
        if j["idx"] == 2:
            continue                      # the straggler: deadline's job
        if j["idx"] == 1 and not j["failed_before"]:
            if age > 1.0:
                j["status"] = "failed"
                j["reason"] = "overexposed frames in the opening seconds"
                j["failed_before"] = True
        elif age > 2.0:
            j["status"] = "done"
            j["url"] = f"prebaked/shot_{j['idx']}.mp4"
    _save(d)
    return d["jobs"]


def reset() -> None:
    config.BROKER.unlink(missing_ok=True)
