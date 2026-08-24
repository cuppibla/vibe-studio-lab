"""Wall platform client. The Wall lives inside the Studio server, but the agent
talks to it the way it would talk to YouTube: over an HTTP contract."""
import httpx

from agent import config


def join(handle: str) -> dict:
    r = httpx.post(f"{config.STUDIO_URL}/api/join", json={"handle": handle}, timeout=10)
    r.raise_for_status()
    return r.json()


def trends() -> list[dict]:
    r = httpx.get(f"{config.STUDIO_URL}/api/trends", timeout=10)
    r.raise_for_status()
    return r.json()["trends"]


def outcomes(creator_id: str) -> list[dict]:
    r = httpx.get(f"{config.STUDIO_URL}/api/outcomes",
                  params={"creator_id": creator_id}, timeout=10)
    r.raise_for_status()
    return r.json()["videos"]


def publish(creds: dict, run_id: str, *, title, description, duration_ms, lap,
            video_ref, thumb_ref, lineage) -> dict:
    r = httpx.post(
        f"{config.STUDIO_URL}/api/publish",
        headers={"Idempotency-Key": run_id},
        json={"creator_id": creds["creator_id"], "token": creds["token"],
              "title": title, "description": description, "duration_ms": duration_ms,
              "lap": lap, "video_ref": video_ref, "thumb_ref": thumb_ref,
              "lineage": lineage},
        timeout=10)
    r.raise_for_status()
    return r.json()
