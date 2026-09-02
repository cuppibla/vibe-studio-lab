"""Stage 1 - the research department, drawn. The FRONT of the real graph.

Nothing here is a copy: the four readers, the join and the composer are
imported from agent/graph.py - the exact functions the finished channel
runs. This app just declares a SUBSET of the final edge list, so you can
run the front of the graph on its own, today, with nothing else built.

Empty memory and an unbuilt BigQuery graph return honest empties - the
same graceful behavior the real lap relies on before the later chapters
fill them. scan_trends is the control group: it has data on day one.
"""
from google.adk import Workflow
from google.adk.workflow import START, JoinNode

from agent.graph import (compose_bundle, read_backcatalog, read_graph,
                         read_memory, scan_trends)

join_research = JoinNode(name="join_research")

root_agent = Workflow(
    name="stage1_fanout",
    description="4 real readers -> join -> one research bundle",
    edges=[(START, scan_trends, join_research),
           (START, read_memory, join_research),
           (START, read_backcatalog, join_research),
           (START, read_graph, join_research),
           (join_research, compose_bundle)])
