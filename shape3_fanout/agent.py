"""③ A FAN-OUT AND A JOIN - plus the two things every real graph has:
an AGENT as a node, and another WORKFLOW as a node.

Run it in adk web: pick `shape3_fanout` and send tonight's TOPIC,
e.g.   laundry night

    START ─┬─ read_trends  ─┐
           ├─ read_memory  ─┤ join_desk ─ pitch(agent) ─ shape2_router ─ announce
           └─ read_history ─┘

The three readers leave START together. The join holds until all three have
landed. `pitch` is a model call - a plain node in the same graph, and it
reads the three keys the readers wrote. Then the WHOLE of shape ② runs as
one box inside this one.
"""
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))

from google.adk import Agent, Event, Workflow  # noqa: E402
from google.adk.workflow import START, JoinNode  # noqa: E402

from agent import config  # noqa: E402
from shape2_router.agent import policy_wf  # noqa: E402  ← the shape you just ran


def read_trends(node_input: str):
    yield Event(state={"topic": node_input,                 # your word, into state
                       "trends": "cozy chores · tiny robots · 9pm posting"})
    yield Event(output="trends read")


def read_memory(node_input: str):
    yield Event(state={"memory": "this channel's audience hates cliffhangers"})
    yield Event(output="memory read")


def read_history(node_input: str):
    yield Event(state={"history": "best lap so far: 'Robot folds laundry', 71% watched"})
    yield Event(output="history read")


join_desk = JoinNode(name="join_desk")

# an AGENT is just a node - and {curly keys} are read from the same state
pitch = Agent(
    name="pitch", model=config.MODEL,
    instruction=("Title ONE <=20s video about: {topic}\n"
                 "trends: {trends}\nmemory: {memory}\nhistory: {history}\n"
                 "Reply with the title only, at most 60 characters."))


def announce(node_input):
    return Event(output={"lap_result": node_input})


root_agent = Workflow(
    name="shape3_fanout", description="3 readers -> join -> agent -> router workflow",
    edges=[(START, read_trends, join_desk),
           (START, read_memory, join_desk),
           (START, read_history, join_desk),
           (join_desk, pitch, policy_wf, announce)])
