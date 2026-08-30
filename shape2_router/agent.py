"""② A ROUTER - one node, two exits. The edge carries the label.

Run it in adk web: pick `shape2_router` and send a title TWICE:
    Robot does the dishes         -> route OK    -> publish
    Robot roasts a competitor     -> route BLOCK -> quarantine

Same code, two paths. Shipping is an EDGE, not a sentence in a prompt.
Then make the router yours: see the TODO under BLACKLIST.
"""
from google.adk import Event, Workflow
from google.adk.workflow import START

BLACKLIST = ["competitor", "hateful", "gore"]

# TODO: YOUR TURN - nothing to do yet; the codelab says when. Then: delete the
# "# " on the next line, save, and send a title containing that word. (No
# restart needed - adk web was started with --reload_agents.)
# BLACKLIST += ["cliffhanger"]


def policy_check(node_input: str):
    """One node, one decision: `route` names the edge to take next."""
    hits = [w for w in BLACKLIST if w in node_input.lower()]
    return Event(output={"title": node_input}, state={"policy_hits": hits},
                 route="BLOCK" if hits else "OK")


def publish(node_input):
    return Event(output={"published": True, "title": node_input["title"]})


def quarantine(node_input, policy_hits: list[str] = []):
    """`policy_hits` came from state - the check wrote it on its way past."""
    return Event(output={"published": False, "blocked_by": policy_hits})


policy_wf = Workflow(
    name="shape2_router", description="check -> publish | quarantine",
    edges=[(START, policy_check),
           (policy_check, {"OK": publish, "BLOCK": quarantine})])

root_agent = policy_wf
