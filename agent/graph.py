"""THE workflow - one graph from research to script, with two human doors.

  4 research nodes -> join -> topic_gate (task mode: chats until you accept)
                           -> creative_gate (RequestInput: one structured form)
                           -> persist_prefs -> scripter -> store_script

The graph pauses for PEOPLE (both doors). It never waits for the WORLD -
renders live in the desk session (agent/desk.py), because resuming a graph
re-runs nodes and would re-submit side effects.
"""
import json

from google.adk import Agent, Event, Workflow
from google.adk.events.request_input import RequestInput
from google.adk.workflow import START, JoinNode

from . import config, state
from .schemas import CREATIVE_SCHEMA, Brief, Script


# ── research fan-out (pure compute + reads) ─────────────────────────────────
def scan_trends(node_input):
    from world import platform
    return Event(output={"trends": platform.trends()})


def read_memory(node_input):
    """Fresh Memory Bank retrieve each run; records citable refs + constraints."""
    from . import memory
    try:
        facts = []  # TODO: RECALL — delete me, uncomment below (Codelab S5)
        # facts = memory.recall()
    except Exception as e:  # cloud hiccup -> honest empty, never a crash
        print(f"  [memory] unavailable ({str(e)[:60]}) -> empty")
        facts = []
    entries = [{"ref": f"memory#{m['id'][:8]}", "topic": m["topic"], "fact": m["fact"]}
               for m in facts]
    rules = " ".join(m["fact"] for m in facts if m["topic"] == "CHANNEL_CONSTRAINTS")
    st = state.load()
    st["memory_facts"] = [{"id": m["id"], "ref": m["id"][:8],
                           "topic": m["topic"], "fact": m["fact"]} for m in facts]
    state.save(st)
    yield Event(state={"constraints": rules or "(none yet)"})
    yield Event(output={"memory": entries})


def read_backcatalog(node_input):
    from world import platform
    creds = state.load().get("creds")
    vids = platform.outcomes(creds["creator_id"]) if creds else []
    slim = [{"title": v["title"], "lap": v["lap"], "avg_watch_pct": v["avg_watch_pct"],
             "median_drop_ms": v["median_drop_ms"], "dropped_pct": v["dropped_pct"]}
            for v in vids]
    return Event(output={"backcatalog": slim})


def read_graph(node_input):
    """The measuring instrument: readings; the graph exists before you do."""
    from bqgraph import queries
    report = queries.research_report()
    st = state.load()
    st["graph_query_ids"] = [q["id"].split("#")[1] for q in report.get("queries", [])
                             if q.get("rows")]
    st["graph_report"] = report
    state.save(st)
    return Event(output={"audience_graph": report})


join_research = JoinNode(name="join_research")


def compose_bundle(node_input):
    """Flatten the join payload into the text bundle the topic gate reads."""
    sections = []
    for key in ("scan_trends", "read_memory", "read_backcatalog", "read_graph"):
        payload = node_input.get(key, {})
        (name, value), = payload.items() if payload else (("empty", {}),)
        body = json.dumps(value, ensure_ascii=False, indent=1)
        empty = " (EMPTY)" if not value else ""
        sections.append(f"## {name}{empty}\n{body}")
    return Event(output="\n\n".join(sections))


# ── door 3 · the collaborative topic gate (one word: mode='task') ───────────
topic_gate = Agent(
    name="topic_gate", model=config.MODEL,
    # mode="task",   # TODO: TASK_WORD — uncomment: one word turns on task mode (Codelab S2)
    output_schema=Brief,
    instruction=(
        "You run the creator's short-video channel. The message you received is "
        "tonight's research bundle (trends, channel memory, backcatalog, audience "
        "graph readings).\n"
        "PITCH exactly ONE topic + angle for the next <=20s video. Reply in "
        "exactly two lines:\nTOPIC: <a concrete, filmable, characterful idea — a "
        "scene someone can picture, never a meta content-strategy topic>\n"
        "ANGLE: <the twist, one line>\n"
        "Then chat: if the creator pushes back, revise the pitch (same two-line "
        "format). When they accept, finish the task with the final Brief.\n"
        "Every evidence entry must cite a REAL source: 'trends', 'backcatalog', "
        "'memory#<id>' (ids present in the memory section only), or 'graph#<n>' "
        "(query numbers present in the graph section only). Empty sections are "
        "never cited - never invent evidence.\n"
        "If the memory section contains CHANNEL_CONSTRAINTS rules, your angle "
        "MUST honor them."))


# ── door 2 · the creative gate (RequestInput: one structured form) ──────────
def creative_gate(node_input: Brief):
    yield Event(state={"brief": node_input.model_dump()})
    state.update(brief=node_input.model_dump())          # driver clipboard copy
    prefs = state.load().get("prefs") or {}
    yield RequestInput(
        message="Creative brief - pick the subject, character, and style.",
        response_schema=CREATIVE_SCHEMA,
        payload={"topic": node_input.topic, "angle": node_input.angle,
                 "defaults": prefs})


def persist_prefs(node_input):
    """Your choices outlive this run: `user:` keys are per-user, cross-session."""
    yield Event(state={"choices": node_input})  # TODO: PREFS — delete me, uncomment below (Codelab S3)
    # yield Event(state={"user:prefs": node_input, "choices": node_input})
    state.update(choices=node_input)                     # driver clipboard copy
    yield Event(output=node_input)


# ── pure production: script the approved idea ───────────────────────────────
scripter = Agent(
    name="scripter", model=config.MODEL, output_schema=Script,
    instruction=(
        "Write the production script for this approved video.\n"
        "Topic + angle + evidence: {brief}\n"
        "The creator's creative choices (honor ALL of them - subject, character, "
        "style): {choices}\n"
        "Channel constraints: {constraints}\n"
        "Deliver: title (<=60 chars), description (1-2 sentences), 3-5 tags, an "
        "opening_line, and EXACTLY 3 shots (each one visual sentence for a render "
        "model, starring the chosen character in the chosen style).\n"
        "If constraints include a conclusion-first rule, opening_line must state "
        "the final outcome outright, and only then set conclusion_first=true. "
        "Never claim conclusion_first for a teaser or a question."))


def store_script(node_input: Script):
    st = state.load()
    st["script"] = node_input.model_dump()
    st["duration_ms"] = 12000
    brief = st.get("brief", {})
    evidence = brief.get("evidence", [])
    # citations become lineage; graph citations carry their re-runnable rows
    report = {q["id"]: q for q in st.get("graph_report", {}).get("queries", [])}
    for e in evidence:
        if e["source"] in report:
            e["rows_snapshot"] = report[e["source"]]["rows"]
    lin = st["lineage"]
    lin["topic"] = brief.get("topic", node_input.title)
    lin["angle"] = brief.get("angle", "")
    lin["evidence"] = evidence
    lin["memory_refs"] = sorted({e["source"] for e in evidence
                                 if e["source"].startswith("memory#")})
    lin["graph_refs"] = sorted({e["source"] for e in evidence
                                if e["source"].startswith("graph#")})
    lin["hook"] = {"hook_at_ms": 0 if node_input.conclusion_first else 5000,
                   "conclusion_first": node_input.conclusion_first}
    state.save(st)
    print(f"  script: {node_input.title!r} · {len(node_input.shots)} shots"
          f" · evidence {len(evidence)}")
    yield Event(message="script ready", state={"script_title": node_input.title})


wf = Workflow(
    name="lap", description="research -> two human doors -> script",
    edges=[
        (START, scan_trends, join_research),
        (START, read_memory, join_research),
        (START, read_backcatalog, join_research),
        (START, read_graph, join_research),
        (join_research, compose_bundle, topic_gate, creative_gate,
         persist_prefs, scripter, store_script),
    ])
if not wf.edges:
    raise NotImplementedError("TODO: EDGES — paste the edges from Codelab S2 "
                              "into agent/graph.py")
