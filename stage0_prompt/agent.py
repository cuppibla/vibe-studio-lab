"""Stage 0 - the whole channel as ONE prompt.

Every sentence of the instruction below is a JOB. Over the next two
chapters, each job becomes a NODE in a drawn graph - the codelab's
replacement table maps sentence -> node, one by one. The tools here call
the same sources the graph's research nodes read; only the shape differs.

Run it and watch what you get: research folded into prose you must re-read,
an "agree with the creator" sentence that can be talked past, and a
blacklist the model certifies for itself. Nothing here is checkable.
"""
from google.adk import Agent

from agent import config


def check_trends() -> dict:
    """Read what is trending on the platform right now."""
    from world import platform
    return {"trends": platform.trends()}


def read_back_catalog() -> dict:
    """List the channel's already-published videos and how they performed."""
    from agent import state
    from world import platform
    creds = state.load().get("creds")
    vids = platform.outcomes(creds["creator_id"]) if creds else []
    return {"backcatalog": [{"title": v["title"], "avg_watch_pct": v["avg_watch_pct"]}
                            for v in vids]}


root_agent = Agent(
    name="solo_channel", model=config.MODEL,
    tools=[check_trends, read_back_catalog],
    instruction=(
        "You run the creator's short-video channel, alone.\n"
        "When the creator gives you an idea (or nothing), do ALL of this:\n"
        "check what is trending. look at your back catalog. propose a "
        "direction and agree on it with the creator. refuse blacklisted "
        "subjects (competitor, hateful, gore). then describe the video you "
        "would make: a title (<=60 chars) and 3 shots, one visual sentence "
        "each.\n"
        "Ask the creator to confirm the direction before describing the "
        "video."))
