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


def request_thumb_approval(thumb_ref: str) -> dict:
    """Show the generated thumbnail to the human. The answer arrives later."""
    return {"status": "pending", "kind": "thumb", "thumb_ref": thumb_ref}


render_desk = Agent(
    name="render_desk", model=config.MODEL,
    tools=[LongRunningFunctionTool(render_submit)],
    instruction=("Call render_submit once PER shot in the given list, all in this same "
                 "turn. If later asked to render an additional retake shot, call "
                 "render_submit once for it. While any submitted shot is pending reply "
                 "exactly WAITING. Only when every submitted shot has status 'done' or "
                 "'replaced', reply ONLY with JSON mapping shot description -> url."))

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
