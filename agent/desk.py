"""The desk - where the WORLD's waits live. Plain agents + LongRunningFunctionTool:
the graph never waits for renders (resume would re-submit); these sessions do.
The join is the driver's to count, never the model's."""
from google.adk import Agent
from google.adk.tools import LongRunningFunctionTool

from . import config
from .schemas import RepairedPrompt


def render_submit(shot_description: str) -> dict:
    """Submit ONE shot to the render farm. Returns immediately; the result arrives later."""
    from world import broker
    job_id = broker.submit(shot_description)
    return {"status": "pending", "job_id": job_id, "shot": shot_description}


def avatar_submit(description: str) -> dict:
    """Draw YOUR creator avatar. `description` is just the character in a few
    words - the studio adds its own house style. Returns immediately; the
    portrait itself takes ~20-30 seconds and arrives later."""
    from world import portrait
    job_id = portrait.submit(description)
    return {"status": "pending", "job_id": job_id, "kind": "avatar",
            "description": description}


def avatar_restyle(change: str) -> dict:
    """Change YOUR existing avatar - a hat, a scarf, a frame. Continues from
    the portrait already on file, so the character stays the same. Returns
    immediately; the new version arrives later."""
    from world import portrait
    latest = portrait.latest()
    if not latest:
        return {"status": "error", "reason": "no avatar yet - call avatar_submit first"}
    job_id = portrait.submit(change, parent=latest["id"])
    return {"status": "pending", "job_id": job_id, "kind": "avatar",
            "change": change, "from": latest["id"]}


def request_thumb_approval(thumb_ref: str) -> dict:
    """Show the generated thumbnail to the human. The answer arrives later."""
    return {"status": "pending", "kind": "thumb", "thumb_ref": thumb_ref}


def remember_avatar(callback_context) -> None:
    """STATE MANAGEMENT, THE CALLBACK WAY.

    Runs after every desk turn. If the portrait studio has a finished avatar,
    record it on the USER - `user:` keys outlive this session, so tomorrow's
    session already knows your face. Writing to callback_context.state is all it takes:
    ADK turns the change into a state delta on the event log for you."""
    from world import portrait
    latest = portrait.latest()
    if not latest:
        return
    state, url, who = callback_context.state, latest["url"], portrait.anchor(latest)
    if state.get("user:avatar") != url or state.get("user:avatar_anchor") != who:
        state["user:avatar"] = url          # user: = this user, every session
        state["user:avatar_anchor"] = who   # the words that started it, from the ledger


render_desk = Agent(
    name="render_desk", model=config.MODEL,
    after_agent_callback=remember_avatar,
    tools=[LongRunningFunctionTool(avatar_submit),
           LongRunningFunctionTool(avatar_restyle),
           LongRunningFunctionTool(render_submit)],
    instruction=(
        "You are the studio desk. Slow work reaches you in three shapes.\n"
        "NEW AVATAR: asked for an avatar, portrait or profile picture -> call "
        "avatar_submit exactly once. Pass ONLY the character words the user gave "
        "you (for example 'a cute cat'); never invent a visual style, the studio "
        "owns that.\n"
        "CHANGE THE AVATAR: asked to add or change something on an existing avatar "
        "(a hat, glasses, a scarf, a frame) -> call avatar_restyle exactly once "
        "with just that change.\n"
        "SHOTS: given shots to render -> call render_submit once PER shot, all in "
        "this same turn; if later asked for an additional retake shot, call "
        "render_submit once for it.\n"
        "While anything you submitted is still pending, reply exactly WAITING.\n"
        "When an avatar job comes back 'done', reply exactly AVATAR READY.\n"
        "When every submitted shot has status 'done' or 'replaced', reply ONLY with "
        "JSON mapping shot description -> url."))

thumb_desk = Agent(
    name="thumb_desk", model=config.MODEL,
    tools=[LongRunningFunctionTool(request_thumb_approval)],
    instruction=("Call request_thumb_approval exactly once with the thumb_ref you were "
                 "given. When it returns status 'approved' or 'rejected', reply with "
                 "ONLY that word in caps."))

prompt_medic = Agent(
    name="prompt_medic", model=config.MODEL, output_schema=RepairedPrompt,
    instruction=("A render failed. You get the original shot prompt and the failure "
                 "reason. Rewrite the prompt to avoid that failure (keep the creative "
                 "intent, change what caused the failure). Explain what_changed in one "
                 "sentence."))
