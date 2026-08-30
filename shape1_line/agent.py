"""① A LINE - the smallest workflow there is: two nodes, one arrow.

Run it in adk web: pick `shape1_line` in the app dropdown (top left) and
send any video title, e.g.   Robot does the dishes

Watch node 2. It never sees node 1's output - it asks for `slug`, and ADK
binds that parameter straight from the run's STATE: the shared notebook
every node in a workflow writes to and reads from.
"""
import re

from google.adk import Event, Workflow
from google.adk.workflow import START


def slugify(node_input: str):
    """Node 1 - writes ONE key into the run's shared state."""
    slug = "-".join(re.findall(r"[a-z0-9]+", node_input.lower()))[:40]
    yield Event(state={"slug": slug or "untitled"})
    yield Event(output={"title": node_input})


def name_the_file(node_input, slug: str = "untitled"):
    """Node 2 - nobody passed `slug` in. ADK looked it up in state."""
    return Event(output={"file": f"{slug}.mp4", "read_from_state": slug})


root_agent = Workflow(
    name="shape1_line", description="a line: slugify -> name_the_file",
    edges=[(START, slugify, name_the_file)])
