"""Stage 2 - the pause. Stage 1 plus the proposer and the human door.

propose_directions turns the research bundle into THREE typed candidates
and writes them into shared STATE; direction_gate suspends the run on a
small form - the same RequestInput hinge as the thumbnail draft's response
box, now structural. You answer with just "1", "2" or "3" (or custom).
What the solo prompt could be talked out of, this graph cannot skip.

The kill test lives here: suspend at the form, Ctrl+C the server, restart,
reopen the session - the form is still standing, because a pause is a row,
not a thread. (Research nodes re-run on resume; they only read, so
re-running is safe - which is exactly why people-pauses are legal in-graph
and machine waits are not.)
"""
from google.adk import Workflow
from google.adk.workflow import START, JoinNode

from agent.graph import (compose_bundle, direction_gate, persist_direction,
                         propose_directions, read_backcatalog, scan_trends)

join_research = JoinNode(name="join_research")

root_agent = Workflow(
    name="stage2_direction",
    description="research -> 3 candidates in state -> the human door",
    edges=[(START, scan_trends, join_research),
           (START, read_backcatalog, join_research),
           (join_research, compose_bundle, propose_directions, direction_gate,
            persist_direction)])
