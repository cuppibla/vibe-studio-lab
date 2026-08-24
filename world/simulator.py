"""Deterministic audience simulator.

Design contract (product-design-v2 §8):
- seed = sha256(viewer_id + video_id)  -> every (viewer, video) pair is reproducible
- drop behavior is derived from persona params x lineage-parsed features
- reward feature = "conclusion-first opening" (NOT hook position - anti-circularity)
- every synthetic view carries is_synthetic=True
"""
from __future__ import annotations

import hashlib
import random
from dataclasses import dataclass


@dataclass(frozen=True)
class Persona:
    archetype: str          # quickcut | slowburn | casual
    patience: float         # base fraction of the video they tend to watch
    conclusion_bonus: float # extra watch fraction when the opening leads with the answer
    cliff_severity: float   # chance they bail at the hook moment when it arrives late


PERSONAS = {
    "quickcut": Persona("quickcut", patience=0.50, conclusion_bonus=0.42, cliff_severity=0.80),
    "slowburn": Persona("slowburn", patience=0.90, conclusion_bonus=0.05, cliff_severity=0.35),
    "casual":   Persona("casual",   patience=0.65, conclusion_bonus=0.30, cliff_severity=0.60),
}

# 24 synthetic viewers - members of RADAR'S OPT-IN PANEL (stage/seed.py:
# vw_{3k}=quickcut, vw_{3k+1}=slowburn, vw_{3k+2}=mixed~casual). This is the
# Nielsen/qiangua mechanism: the vendor can compute your audience overlap ONLY
# because some of your viewers are panel members - and that's also why your
# video isn't a 2-hop island in the graph.
SYNTHETIC_VIEWERS = (
    [(f"vw_{i*3:03d}", "quickcut") for i in range(10)]
    + [(f"vw_{i*3+2:03d}", "casual") for i in range(8)]
    + [(f"vw_{i*3+1:03d}", "slowburn") for i in range(6)]
)


def _rng(viewer_id: str, video_id: str) -> random.Random:
    seed = hashlib.sha256(f"{viewer_id}:{video_id}".encode()).hexdigest()
    return random.Random(int(seed[:16], 16))


def simulate_view(viewer_id: str, archetype: str, video_id: str,
                  duration_ms: int, lineage: dict) -> dict:
    """One deterministic synthetic view."""
    p = PERSONAS[archetype]
    rng = _rng(viewer_id, video_id)

    hook = (lineage or {}).get("hook") or {}
    conclusion_first = bool(hook.get("conclusion_first"))
    hook_at_ms = int(hook.get("hook_at_ms", 5000))

    if not conclusion_first and rng.random() < p.cliff_severity:
        # bail shortly after realizing the answer isn't coming
        drop_ms = min(duration_ms, hook_at_ms - int(rng.random() * 1500))
        drop_ms = max(800, drop_ms)
        return _row(viewer_id, video_id, watched=drop_ms, drop=drop_ms,
                    completed=False, duration_ms=duration_ms)

    frac = p.patience + (p.conclusion_bonus if conclusion_first else 0.0)
    frac *= 0.85 + 0.3 * rng.random()          # +-15% personal noise
    frac = max(0.05, min(1.0, frac))
    watched = int(duration_ms * frac)
    completed = frac >= 0.90
    return _row(viewer_id, video_id, watched=watched,
                drop=None if completed else watched,
                completed=completed, duration_ms=duration_ms)


def _row(viewer_id, video_id, watched, drop, completed, duration_ms):
    return {
        "viewer_id": viewer_id,
        "video_id": video_id,
        "watched_ms": watched,
        "drop_ms": drop,
        "completed": completed,
        "duration_ms": duration_ms,
        "is_synthetic": True,
    }


def simulate_audience(video_id: str, duration_ms: int, lineage: dict) -> list[dict]:
    return [simulate_view(v, a, video_id, duration_ms, lineage)
            for v, a in SYNTHETIC_VIEWERS]
