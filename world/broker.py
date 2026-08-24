"""PREBAKED render broker (file-backed, survives process boundaries).

Deterministic by submission order within a lap:
  job 0      -> done after 2s (prebaked url)
  job 1      -> FAILS once ("overexposed frames"); a resubmission succeeds after 2s
  job 2      -> never completes (the deadline must rescue it)
  job 3+     -> done after 2s   (repair resubmissions land here)
Pull-through advancement: state only moves when poll() is called - no daemon.
"""
import json
import time

from agent import config


def _load() -> dict:
    if config.BROKER.exists():
        return json.loads(config.BROKER.read_text())
    return {"jobs": []}


def _save(d) -> None:
    config.BROKER.write_text(json.dumps(d, indent=2))


def submit(prompt: str) -> str:
    d = _load()
    idx = len(d["jobs"])
    job = {"id": f"job_{idx}", "idx": idx, "prompt": prompt,
           "status": "queued", "submitted_at": time.time(), "failed_before": False}
    d["jobs"].append(job)
    _save(d)
    return job["id"]


def poll() -> list[dict]:
    """Advance and return all jobs. Deterministic per the order table above."""
    d = _load()
    now = time.time()
    for j in d["jobs"]:
        if j["status"] != "queued":
            continue
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
