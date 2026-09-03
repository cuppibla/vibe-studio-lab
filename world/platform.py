"""Wall platform client. The Wall lives inside the Studio server, but the agent
talks to it the way it would talk to YouTube: over an HTTP contract."""
import httpx

from agent import config

# The wall's trend feed. Vibe Studio serves this list on /api/trends; the
# research node asks Studio first and falls back to the same list when the
# app is not running yet (the stage apps run BEFORE Vibe Studio is booted).
SEED_TRENDS = [
    {"topic": "tiny robots doing household chores (badly)", "heat": 91},
    {"topic": "pets reviewing kitchen gadgets", "heat": 84},
    {"topic": "desk toys with secret lives after midnight", "heat": 77},
    {"topic": "speedrunning the most boring chore you know", "heat": 66},
    {"topic": "kitchen science that looks illegal in 10 seconds", "heat": 58},
]


def join(handle: str) -> dict:
    r = httpx.post(f"{config.STUDIO_URL}/api/join", json={"handle": handle}, timeout=10)
    r.raise_for_status()
    return r.json()


def trends() -> list[dict]:
    try:
        r = httpx.get(f"{config.STUDIO_URL}/api/trends", timeout=10)
        r.raise_for_status()
        return r.json()["trends"]
    except httpx.HTTPError:          # Studio not up yet (the stage apps): same list
        print("  [platform] Vibe Studio is not running - using the seed trend list")
        return list(SEED_TRENDS)


def outcomes(creator_id: str) -> list[dict]:
    try:
        r = httpx.get(f"{config.STUDIO_URL}/api/outcomes",
                      params={"creator_id": creator_id}, timeout=10)
        r.raise_for_status()
        return r.json()["videos"]
    except httpx.HTTPError:          # no wall yet -> an honestly empty back catalog
        return []


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
