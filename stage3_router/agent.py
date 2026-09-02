"""Stage 3 - the policy gate, and the base graph is complete.

Stage 2 plus the deterministic ROUTER: policy_check reads
agent/policy_words.txt at DECISION time and routes your chosen direction
to OK or BLOCK - before any script is written, any render submitted, any
money spent. BLOCK ends at quarantine, the polite stop.

This edge list is the one you will write into agent/graph.py yourself at
the EDGES hole: by then it is a recital, not a leap. (The scripter at the
tail runs quietly - the lap needs a script for renders and titles, but the
codelab spends no time on it.)
"""
from google.adk import Workflow
from google.adk.workflow import START, JoinNode

from agent.graph import (compose_bundle, direction_gate, persist_direction,
                         policy_check, propose_directions, quarantine,
                         read_backcatalog, scan_trends, scripter, store_script)

join_research = JoinNode(name="join_research")

root_agent = Workflow(
    name="stage3_router",
    description="the complete base graph: research -> you -> the policy gate",
    edges=[(START, scan_trends, join_research),
           (START, read_backcatalog, join_research),
           (join_research, compose_bundle, propose_directions, direction_gate,
            persist_direction, policy_check),
           (policy_check, {"OK": scripter, "BLOCK": quarantine}),
           (scripter, store_script)])
