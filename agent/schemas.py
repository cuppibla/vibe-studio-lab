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
    line); Vibe Studio renders the same schema as a radio list.

    NOTHING is `required` here, and that is load-bearing - do not "tidy" it
    back. ADK re-validates a STORED interrupt response against this schema on
    EVERY resume (_rehydration_utils._validate_resume_response), and that
    function builds its pydantic model straight off `required`:

        prop_type = type_mapping.get(prop_type_str, Any)
        if prop_name in required: fields[n] = (prop_type, ...)         # no None
        else:                     fields[n] = (prop_type | None, None) # nullable

    So `required` is the ONLY lever a JSON-Schema dict has here. A dev UI that
    submits the form with nothing selected stores `{"pick": null}`; with
    "pick" required that null can never validate again, so the session is
    poisoned FOREVER - every later resume dies before a line of our code runs,
    and surfaces (misleadingly) as a replay-divergence timeout downstream.
    The alternatives do not work: `"type": ["string", "null"]` is a LIST, and
    `type_mapping.get(<list>)` raises `TypeError: unhashable type: 'list'`;
    OpenAPI-style `"nullable": true` is simply never read; and a JSON-Schema
    `"default"` is not applied by ADK while the field stays required.

    The form still says what it means: the enum lists the real choices and the
    description spells out what a blank means. persist_direction() resolves a
    null / missing / empty / garbage pick to candidate 1 (or to `custom` when
    you typed one), so the default lives in code, where it can actually run.
    """
    picks = [str(i + 1) for i in range(n_candidates)] + ["custom"]
    return {
        "type": "object",
        "properties": {
            "pick": {"type": "string", "enum": picks, "default": "1",
                     "description": f"1..{n_candidates} chooses a candidate; "
                                    "custom uses your own. Leave it blank and "
                                    "you get 1 (or your custom line, if you "
                                    "typed one)."},
            "custom": {"type": "string", "default": "",
                       "description": "your own direction (read when pick=custom, "
                                      "or when pick is blank)"},
        },
        # Deliberately empty: see the docstring. A stored null must stay
        # rehydratable, or the learner's session can never be resumed again.
        "required": [],
    }
