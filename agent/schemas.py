"""Typed contracts between nodes - the workflow passes OBJECTS, not vibes."""
from pydantic import BaseModel, Field


class Evidence(BaseModel):
    claim: str
    source: str          # "trends" | "memory#<id>" | "graph#<n>" | "backcatalog"


class Brief(BaseModel):
    topic: str
    angle: str
    evidence: list[Evidence]


class CreativeChoices(BaseModel):
    subject: str
    character: str
    style: str            # low-poly | paper | bright


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


CREATIVE_SCHEMA = {
    "type": "object",
    "properties": {
        "subject": {"type": "string"},
        "character": {"type": "string"},
        "style": {"type": "string", "enum": ["low-poly", "paper", "bright"]},
    },
    "required": ["subject", "character", "style"],
}
