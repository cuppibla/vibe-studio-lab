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
               '''    raise NotImplementedError("TODO: RESUME — delete me, uncomment the delivery below (Codelab ⏳)")
    # part = gtypes.Part(function_response=gtypes.FunctionResponse(
    #     id=call_id, name=name, response=response))
    # return await _drive(node, session_id, [part], user_id)''',
               '''    part = gtypes.Part(function_response=gtypes.FunctionResponse(
        id=call_id, name=name, response=response))
    return await _drive(node, session_id, [part], user_id)'''),

    # Act II · workflow — the base graph, drawn by you
    "EDGES": ("agent/graph.py",
              '''        # TODO: EDGES — delete me, uncomment the base graph below (Codelab 🗺️, the EDGES hole)
        # (START, scan_trends, join_research),
        # (START, read_backcatalog, join_research),
        # (join_research, compose_bundle, propose_directions, direction_gate,
        #  persist_direction, policy_check),
        # (policy_check, {"OK": scripter, "BLOCK": quarantine}),
        # (scripter, store_script),''',
              '''        (START, scan_trends, join_research),
        (START, read_backcatalog, join_research),
        (join_research, compose_bundle, propose_directions, direction_gate,
         persist_direction, policy_check),
        (policy_check, {"OK": scripter, "BLOCK": quarantine}),
        (scripter, store_script),'''),

    # Act III · the audience graph joins the fan-out — one edge
    "GRAPH_EDGE": ("agent/graph.py",
                   '''        # TODO: GRAPH_EDGE — delete me, uncomment below: the audience graph joins the fan-out (Codelab 🌍)
        # (START, read_graph, join_research),''',
                   '''        (START, read_graph, join_research),'''),

    # Act III · the memory bank joins the fan-out — one edge
    "MEMORY_EDGE": ("agent/graph.py",
                    '''        # TODO: MEMORY_EDGE — delete me, uncomment below: the channel's memory joins the fan-out (Codelab 🧠)
        # (START, read_memory, join_research),''',
                    '''        (START, read_memory, join_research),'''),

    # S2 · the join is yours
    "JOIN_CONDITION": ("agent/joinlogic.py",
                       '''    raise NotImplementedError("TODO: JOIN_CONDITION — delete me, uncomment the two lines below (Codelab 🏁)")
    # still = drive.run(drive.pending(desk_sid(st)))
    # human_ok = any(a["kind"] == "thumb" for a in st["lineage"]["approvals"])''',
                       '''    still = drive.run(drive.pending(desk_sid(st)))
    human_ok = any(a["kind"] == "thumb" for a in st["lineage"]["approvals"])'''),

    # S4 · a graph is a lens over tables — one edge is the vocabulary
    "EDGE_TABLE": ("bqgraph/load.py",
                   '''    -- TODO: EDGE_TABLE — delete me, uncomment the watched edge below (Codelab 🌍)
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
                 '''    raise NotImplementedError("TODO: GENERATE — delete me, uncomment the write below (Codelab 🧠)")
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

}

# codelab section aliases for rescue
SECTIONS = {"s1": ["RESUME"], "s2": ["EDGES", "JOIN_CONDITION"],
            "s4": ["EDGE_TABLE", "GRAPH_EDGE"], "s5": ["GENERATE", "MEMORY_EDGE"]}
