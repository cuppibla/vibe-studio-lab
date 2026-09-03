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


def thumb_submit(idea: str, caption: str) -> dict:
    """Draw a draft thumbnail for a video idea. `idea` is just the scene in a
    few words - the studio adds its own house style. `caption` is the 2-4
    word sticker printed on the picture (you write it). Returns immediately;
    the picture itself takes ~20-30 seconds and arrives later."""
    from world import thumbstudio
    job_id = thumbstudio.submit(idea, caption=caption)
    return {"status": "pending", "job_id": job_id, "kind": "thumb_draft",
            "idea": idea, "caption": caption}


def thumb_revise(change: str) -> dict:
    """Change the existing draft thumbnail - warmer light, a prop, a mood.
    Continues from the draft already on file, so the scene stays the same.
    Returns immediately; the new version arrives later."""
    from world import thumbstudio
    latest = thumbstudio.latest()
    if not latest:
        return {"status": "error", "reason": "no draft yet - call thumb_submit first"}
    job_id = thumbstudio.submit(change, parent=latest["id"])
    return {"status": "pending", "job_id": job_id, "kind": "thumb_draft",
            "change": change, "from": latest["id"]}


def request_thumb_approval(thumb_ref: str) -> dict:
    """Show the generated thumbnail to the human. The answer arrives later."""
    return {"status": "pending", "kind": "thumb", "thumb_ref": thumb_ref}


def remember_thumb(callback_context) -> None:
    """STATE MANAGEMENT, THE CALLBACK WAY.

    Runs after every desk turn. If the thumbnail studio has a finished draft,
    record it on the USER - `user:` keys outlive this session, so tomorrow's
    session already knows your taste. Writing to callback_context.state is all
    it takes: ADK turns the change into a state delta on the event log for you."""
    from world import thumbstudio
    latest = thumbstudio.latest()
    if not latest:
        return
    state, url, idea = callback_context.state, latest["url"], thumbstudio.anchor(latest)
    if state.get("user:thumb_draft") != url or state.get("user:thumb_idea") != idea:
        state["user:thumb_draft"] = url     # user: = this user, every session
        state["user:thumb_idea"] = idea     # the idea that started it, from the ledger


render_desk = Agent(
    name="render_desk", model=config.MODEL,
    after_agent_callback=remember_thumb,
    tools=[LongRunningFunctionTool(thumb_submit),
           LongRunningFunctionTool(thumb_revise),
           LongRunningFunctionTool(render_submit)],
    instruction=(
        "You are the studio desk. Slow work reaches you in three shapes.\n"
        "NEW DRAFT: asked for a thumbnail for a video idea -> call thumb_submit "
        "exactly once. idea = ONLY the scene words the user gave you (for example "
        "'a tiny robot doing laundry at midnight'); never invent a visual style, "
        "the studio owns that. caption = 2-4 punchy Title Case words YOU write "
        "for the sticker on the picture (for example 'Laundry Night Chaos') - "
        "the feeling of the moment, no punctuation, no emoji.\n"
        "REVISE THE DRAFT: asked to change something on the existing draft "
        "(light, mood, a prop, a color) -> call thumb_revise exactly once with "
        "just that change.\n"
        "SHOTS: given shots to render -> call render_submit once PER shot, all in "
        "this same turn; if later asked for an additional retake shot, call "
        "render_submit once for it.\n"
        "While anything you submitted is still pending, reply exactly WAITING.\n"
        "When a thumbnail draft comes back 'approved', reply exactly THUMBNAIL "
        "APPROVED. When it comes back 'done', reply exactly DRAFT READY.\n"
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
