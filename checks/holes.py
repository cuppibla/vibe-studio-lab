"""THE HOLE REGISTRY - single source of truth for every hole in the lab.

Every hole is UNCOMMENT-style: the carved starter carries a TODO line (or a
loud raise) plus the real solution commented out right below it. The student
deletes the TODO/raise line and uncomments the block - no copy-paste.

Each hole: file · anchor (what the CARVED starter contains) · snippet (the
filled lines; byte-identical to solutions/). Consumed by:
  scripts/carve.py    filled -> carved   (ships the starter)
  scripts/rescue.py   carved -> filled   (one hole at a time, for the stuck)
  checks/verify_holes.py  proves carve+all-snippets == solutions, byte for byte
  checks/verify_pastes.py additionally proves CODELAB.md code blocks == snippets
"""

HOLES = {
    # S1 · long running — delivering a result, the three lines
    "RESUME": ("agent/drive.py",
               '''    raise NotImplementedError("TODO: RESUME — delete me, uncomment the delivery below (Codelab S1)")
    # part = gtypes.Part(function_response=gtypes.FunctionResponse(
    #     id=call_id, name=name, response=response))
    # return await _drive(node, session_id, [part], user_id)''',
               '''    part = gtypes.Part(function_response=gtypes.FunctionResponse(
        id=call_id, name=name, response=response))
    return await _drive(node, session_id, [part], user_id)'''),

    # S2 · workflow — the shape is the parallelism
    "EDGES": ("agent/graph.py",
              '''        # TODO: EDGES — delete me, uncomment the shape below (Codelab S2)
        # (START, scan_trends, join_research),
        # (START, read_memory, join_research),
        # (START, read_backcatalog, join_research),
        # (START, read_graph, join_research),
        # (join_research, compose_bundle, topic_gate, creative_gate,
        #  persist_prefs, scripter, store_script),''',
              '''        (START, scan_trends, join_research),
        (START, read_memory, join_research),
        (START, read_backcatalog, join_research),
        (START, read_graph, join_research),
        (join_research, compose_bundle, topic_gate, creative_gate,
         persist_prefs, scripter, store_script),'''),

    # S2 · the graph asks a person, one structured form
    "CREATIVE_GATE": ("agent/graph.py",
                      '''    raise NotImplementedError("TODO: CREATIVE_GATE — delete me, uncomment below (Codelab S2)")
    # yield RequestInput(
    #     message="Creative brief - pick the subject, character, and style.",
    #     response_schema=CREATIVE_SCHEMA,
    #     payload={"topic": node_input.topic, "angle": node_input.angle,
    #              "defaults": prefs})''',
                      '''    yield RequestInput(
        message="Creative brief - pick the subject, character, and style.",
        response_schema=CREATIVE_SCHEMA,
        payload={"topic": node_input.topic, "angle": node_input.angle,
                 "defaults": prefs})'''),

    # S2 · the join is yours
    "JOIN_CONDITION": ("agent/joinlogic.py",
                       '''    raise NotImplementedError("TODO: JOIN_CONDITION — delete me, uncomment the two lines below (Codelab S2)")
    # still = drive.run(drive.pending(desk_sid(st)))
    # human_ok = any(a["kind"] == "thumb" for a in st["lineage"]["approvals"])''',
                       '''    still = drive.run(drive.pending(desk_sid(st)))
    human_ok = any(a["kind"] == "thumb" for a in st["lineage"]["approvals"])'''),

    # S3 · prefs are state — one word, one lifetime
    "PREFS": ("agent/graph.py",
              '''    yield Event(state={"choices": node_input})  # TODO: PREFS — delete me, uncomment below (Codelab S3)
    # yield Event(state={"user:prefs": node_input, "choices": node_input})''',
              '    yield Event(state={"user:prefs": node_input, "choices": node_input})'),

    # S4 · a graph is a lens over tables — one edge is the vocabulary
    "EDGE_TABLE": ("bqgraph/load.py",
                   '''    -- TODO: EDGE_TABLE — delete me, uncomment the watched edge below (Codelab S4)
    -- `{d}.watched` AS watched
    --   KEY (viewer_id, video_id)
    --   SOURCE KEY (viewer_id) REFERENCES viewers (id)
    --   DESTINATION KEY (video_id) REFERENCES videos (id)''',
                   '''    `{d}.watched` AS watched
      KEY (viewer_id, video_id)
      SOURCE KEY (viewer_id) REFERENCES viewers (id)
      DESTINATION KEY (video_id) REFERENCES videos (id)'''),

    # S5 · learned state — the WRITE path
    "GENERATE": ("agent/memory.py",
                 '''    raise NotImplementedError("TODO: GENERATE — delete me, uncomment the write below (Codelab S5)")
    # op = _cli().agent_engines.memories.generate(
    #     name=name,
    #     direct_memories_source=vt.GenerateMemoriesRequestDirectMemoriesSource(
    #         direct_memories=[{"fact": f} for f in facts]),
    #     scope=SCOPE, config={"wait_for_completion": True})''',
                 '''    op = _cli().agent_engines.memories.generate(
        name=name,
        direct_memories_source=vt.GenerateMemoriesRequestDirectMemoriesSource(
            direct_memories=[{"fact": f} for f in facts]),
        scope=SCOPE, config={"wait_for_completion": True})'''),

    # S5 · the READ path — one line closes the loop
    "RECALL": ("agent/graph.py",
               '''        facts = []  # TODO: RECALL — delete me, uncomment below (Codelab S5)
        # facts = memory.recall()''',
               '        facts = memory.recall()'),
}

# codelab section aliases for rescue
SECTIONS = {"s1": ["RESUME"], "s2": ["EDGES", "CREATIVE_GATE", "JOIN_CONDITION"],
            "s3": ["PREFS"], "s4": ["EDGE_TABLE"], "s5": ["GENERATE", "RECALL"]}
