"""Stage 3 - the script. Stage 2 plus scripter and store_script, and that
is the COMPLETE lap graph, edge for edge.

"Why a script" answers itself here, not at the start: the script is what
everything upstream was FOR - real readings, the desk's Brief, your form
choices, the channel's constraints, landing in one deliverable the render
farm needs next. store_script files it in the ledger with its evidence
citations - the lineage the publish gates will read.

This edge list is the one you will write into agent/graph.py yourself at
the EDGES hole: by then it is a recital, not a leap.
"""
from google.adk import Workflow
from google.adk.workflow import START, JoinNode

from agent.graph import (compose_bundle, creative_gate, persist_prefs,
                         read_backcatalog, read_graph, read_memory,
                         scan_trends, scripter, store_script, topic_gate)

join_research = JoinNode(name="join_research")

root_agent = Workflow(
    name="stage3_script",
    description="the complete lap graph: research -> the human door -> script",
    edges=[(START, scan_trends, join_research),
           (START, read_memory, join_research),
           (START, read_backcatalog, join_research),
           (START, read_graph, join_research),
           (join_research, compose_bundle, topic_gate, creative_gate,
            persist_prefs, scripter, store_script)])
