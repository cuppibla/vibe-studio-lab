"""Typed contracts between nodes - the workflow passes OBJECTS, not vibes."""
from pydantic import BaseModel, Field


class Evidence(BaseModel):
    claim: str
    source: str          # "trends" | "memory#<id>" | "graph#<n>" | "backcatalog"


class Brief(BaseModel):
    topic: str
    angle: str
    evidence: list[Evidence]


class Direction(BaseModel):
    title: str           # <=60 chars, filmable, characterful
    angle: str           # the twist, one line
    hook: str = ""       # 2-4 words printed as the thumbnail's sticker
    evidence: list[Evidence]


class Directions(BaseModel):
    candidates: list[Direction]   # exactly 3


class Shot(BaseModel):
    description: str


class Script(BaseModel):
    title: str
    description: str
    tags: list[str]
    opening_line: str
    conclusion_first: bool   # true ONLY if opening_line states the outcome outright
    shots: list[Shot]


class RepairedPrompt(BaseModel):
    new_prompt: str
    what_changed: str


def direction_schema(n_candidates: int) -> dict:
    """The form the graph raises at the human door. Built at YIELD time so
    the candidate count is real, not hardcoded - the schema IS the form.
    In the dev UI you type just "1", "2" or "3" (or "custom" plus your own
    line); Vibe Studio renders the same schema as a radio list."""
    picks = [str(i + 1) for i in range(n_candidates)] + ["custom"]
    return {
        "type": "object",
        "properties": {
            "pick": {"type": "string", "enum": picks,
                     "description": "1..N chooses a candidate; custom uses your own"},
            "custom": {"type": "string",
                       "description": "your own direction (only read when pick=custom)"},
        },
        "required": ["pick"],
    }
