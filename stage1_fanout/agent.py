"""Stage 1 - the research department, drawn. The FRONT of the real graph.

Nothing here is a copy: the two readers, the join and the composer are
imported from agent/graph.py - the exact functions the finished channel
runs. This app just declares a SUBSET of the final edge list, so you can
run the front of the graph on its own, today, with nothing else built.

Two readers for now. The fan-out GROWS later: the audience graph joins in
the BigQuery chapter, the memory bank in the Memory Bank chapter - one
edge each, and the map grows a node the moment you add it.
"""
from google.adk import Workflow
from google.adk.workflow import START, JoinNode

from agent.graph import compose_bundle, read_backcatalog, scan_trends

join_research = JoinNode(name="join_research")

root_agent = Workflow(
    name="stage1_fanout",
    description="2 real readers -> join -> one research bundle",
    edges=[(START, scan_trends, join_research),
           (START, read_backcatalog, join_research),
           (join_research, compose_bundle)])
