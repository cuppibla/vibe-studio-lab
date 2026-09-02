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


def recall_lessons() -> dict:
    """Ask the channel's long-term memory for lessons (empty until a bank exists)."""
    from agent import memory
    try:
        return {"lessons": [m["fact"] for m in memory.recall()]}
    except Exception:
        return {"lessons": []}


def read_back_catalog() -> dict:
    """List the channel's already-published videos and how they performed."""
    from agent import state
    from world import platform
    creds = state.load().get("creds")
    vids = platform.outcomes(creds["creator_id"]) if creds else []
    return {"backcatalog": [{"title": v["title"], "avg_watch_pct": v["avg_watch_pct"]}
                            for v in vids]}


def query_audience_graph() -> dict:
    """Query the audience graph for retention readings (empty until it is built)."""
    from bqgraph import queries
    return {"audience_graph": queries.research_report()}


root_agent = Agent(
    name="solo_channel", model=config.MODEL,
    tools=[check_trends, recall_lessons, read_back_catalog, query_audience_graph],
    instruction=(
        "You run the creator's short-video channel, alone.\n"
        "When the creator gives you tonight's topic hint, do ALL of this:\n"
        "check what is trending. recall your lessons. look at your back "
        "catalog. query the audience graph. agree with the creator on a "
        "topic. refuse blacklisted subjects (competitor, hateful, gore). "
        "then write the script: a title (<=60 chars), an opening line, and "
        "EXACTLY 3 shots, one visual sentence each.\n"
        "Ask the creator for their creative choices (subject, character, "
        "style) before writing the script."))
