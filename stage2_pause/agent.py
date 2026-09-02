"""Stage 2 - the pause. Stage 1 plus the topic desk and the human door.

topic_gate turns the research bundle into a typed Brief in ONE call, then
creative_gate suspends the run on a form - the same RequestInput hinge as
your avatar's response box, now structural. What the solo prompt could be
talked out of, this graph physically cannot skip.

The kill test lives here: suspend at the form, Ctrl+C the server, restart,
reopen the session - the form is still standing, because a pause is a row,
not a thread. (Research nodes re-run on resume; they only read, so re-running
is safe - which is exactly why people-pauses are legal in-graph and machine
waits are not.)
"""
from google.adk import Workflow
from google.adk.workflow import START, JoinNode

from agent.graph import (compose_bundle, creative_gate, persist_prefs,
                         read_backcatalog, read_graph, read_memory,
                         scan_trends, topic_gate)

join_research = JoinNode(name="join_research")

root_agent = Workflow(
    name="stage2_pause",
    description="research -> topic desk -> the human door (a form)",
    edges=[(START, scan_trends, join_research),
           (START, read_memory, join_research),
           (START, read_backcatalog, join_research),
           (START, read_graph, join_research),
           (join_research, compose_bundle, topic_gate, creative_gate,
            persist_prefs)])
