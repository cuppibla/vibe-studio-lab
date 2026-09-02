"""Per-section gates:  python -m checks.check <gate>
Gates (codelab order): spinup · pending · workflow · hitl · publish · state ·
graph · memory · loop.  Every assertion is against REAL artifacts (sessions.db /
state.json / wall.db / BigQuery / Memory Bank) - never a source grep."""
import json
import pathlib
import sqlite3
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))
from agent import config, drive, state  # noqa: E402

OK, FAIL = "  ✓", "  ✗"
failures = []


def check(name, cond, detail=""):
    print(f"{FAIL if not cond else OK} {name}" + (f"  [{detail}]" if detail and not cond else ""))
    if not cond:
        failures.append(name)


def st():
    return state.load()


def wall():
    c = sqlite3.connect(config.WALL_DB)
    c.row_factory = sqlite3.Row
    return c


def _session_calls(sid, user=None):
    """(long_running_ids, latest_response_per_id, calls_by_name) for a session."""
    async def _get():
        s = await drive.svc().get_session(app_name=config.APP,
                                          user_id=user or config.USER,
                                          session_id=sid)
        lr, latest, names = set(), {}, {}
        for ev in (s.events if s else []):
            if getattr(ev, "long_running_tool_ids", None):
                lr |= set(ev.long_running_tool_ids)
            for f in ev.get_function_calls() or []:
                names.setdefault(f.name, 0)
                names[f.name] += 1
            for r in ev.get_function_responses() or []:
                latest[r.id] = (r.name, r.response)
        return lr, latest, names
    return drive.run(_get())


def gate_spinup():
    import httpx
    r = httpx.get(f"{config.STUDIO_URL}/api/trends", timeout=5)
    check("Vibe Studio is up (one server, API + console)", r.status_code == 200)
    check("the wall db exists", config.WALL_DB.exists())


def gate_one():
    """Works for BOTH delivery paths: the dev UI's response box and
    `python -m agent.deliver` - all we assert is that some session carried a
    long-running call and that its result came back addressed by the same id."""
    async def _scan():
        service = drive.svc()
        found = []
        for user in ("user", config.USER):
            resp = await service.list_sessions(app_name=config.APP, user_id=user)
            for meta in resp.sessions:
                s = await service.get_session(app_name=config.APP, user_id=user,
                                              session_id=meta.id)
                lr, latest = set(), {}
                for ev in (s.events if s else []):
                    if getattr(ev, "long_running_tool_ids", None):
                        lr |= set(ev.long_running_tool_ids)
                    for r in ev.get_function_responses() or []:
                        latest[r.id] = r.response or {}
                if lr:
                    done = [c for c in lr
                            if latest.get(c, {}).get("status") not in (None, "pending")]
                    found.append((meta.id, len(lr), len(done)))
        return found
    sessions = drive.run(_scan())
    check("a session carried a long-running call", bool(sessions),
          "type a render request in adk web first")
    delivered = [s for s in sessions if s[2] >= 1]
    check("its result was delivered by id (UI box or agent.deliver)",
          bool(delivered), f"open calls still pending in {[s[0] for s in sessions]}")


def gate_pending():
    s = st()
    lr, latest, _ = _session_calls(f"{s['run_id']}_desk")
    check("the desk carried >=3 long-running render calls", len(lr) >= 3, str(len(lr)))
    answered = [cid for cid in lr if cid in latest
                and latest[cid][1].get("status") != "pending"]
    check("every open call got its result delivered (by id)",
          len(answered) == len(lr), f"{len(answered)}/{len(lr)}")
    check("the deadline rescued the straggler", len(s["lineage"]["deadline"]) >= 1)


def gate_workflow():
    s = st()
    check("state has a brief (the workflow ran)", "brief" in s)
    srcs = {e["source"] for e in s["brief"]["evidence"]}
    valid = {"trends", "backcatalog"}
    valid |= {f"memory#{m['ref']}" for m in s.get("memory_facts", [])}
    valid |= {f"graph#{q}" for q in s.get("graph_query_ids", [])}
    check("every evidence source is REAL (no invented citations)",
          srcs <= valid, str(srcs - valid))
    check("a script exists with exactly 3 shots", len(s.get("script", {}).get("shots", [])) == 3)


def gate_hitl():
    s = st()
    lr, latest, names = _session_calls(f"{s['run_id']}_wf")
    check("the graph asked a human via RequestInput (adk_request_input)",
          "adk_request_input" in names)
    ri_answered = any(latest[cid][0] == "adk_request_input" for cid in lr
                      if cid in latest)
    check("the form was answered by function_response (same id)", ri_answered)
    ri_calls = [cid for cid in latest if latest[cid][0] == "adk_request_input"]
    check("exactly ONE human pause in the graph (the form)", len(ri_calls) == 1,
          f"{len(ri_calls)} RequestInput calls")
    check("3 candidate directions were written into state before the ask",
          len(s.get("candidates") or []) == 3, str(len(s.get("candidates") or [])))
    check("your pick became THE direction (state, not prose)",
          bool(s.get("direction")), str(s.get("direction")))
    check("the policy gate ROUTED your direction (OK or BLOCK, recorded)",
          "policy" in (s.get("lineage", {}).get("gates") or {}),
          str(s.get("lineage", {}).get("gates")))


def gate_publish():
    s = st()
    lin = s["lineage"]
    check("published", "published" in s)
    check("the medic repaired one shot (prompt changed)",
          len(lin["repair"]) >= 1 and lin["repair"][0]["original"] != lin["repair"][0]["new_prompt"])
    check("gates ran BEFORE publish and passed",
          lin["gates"].get("policy", {}).get("ok") is True
          and all((lin["gates"].get("eval", {}).get("checks") or {"x": False}).values()))
    import httpx
    r = httpx.post(f"{config.STUDIO_URL}/api/publish",
                   headers={"Idempotency-Key": s["run_id"]},
                   json={"creator_id": s["creds"]["creator_id"], "token": s["creds"]["token"],
                         "title": "REPLAY", "description": "", "duration_ms": 1, "lap": 9,
                         "video_ref": "x", "thumb_ref": "", "lineage": {}})
    check("publish is idempotent (replay returns the ORIGINAL video)",
          r.json().get("video_id") == s["published"]["video_id"])
    v = wall().execute("SELECT COUNT(*) c FROM views WHERE video_id=?",
                       (s["published"]["video_id"],)).fetchone()["c"]
    check("the panel watched immediately (24 synthetic views)", v == 24, str(v))
    check("the thumbnail shipped with the video",
          bool((s.get("thumb") or {}).get("ref")))
    import os
    if os.environ.get("VIBETUBE_URL") and os.environ.get("VIBETUBE_EVENT"):
        check("the room premiere happened silently (state.room has a url)",
              bool((s.get("room") or {}).get("url")),
              str((s.get("room") or {}).get("skipped", "no room record")))
    else:
        print("  - room: not configured — silent premiere skipped (local only)")


def gate_state():
    s = st()
    user_state = drive.run(drive.ensure_user_state("gate_state_probe"))
    prefs = user_state.get("user:prefs") or {}
    check("user:prefs survives OUTSIDE any run's session",
          bool(prefs.get("last_direction")))
    check("prefs remember THE direction you picked",
          prefs.get("last_direction") == s.get("direction"), str(prefs))
    check("no temp: keys leaked into durable state",
          not [k for k in user_state if k.startswith("temp:")])


def gate_graph():
    from agent.graph import wf
    check("read_graph is WIRED into the fan-out (the GRAPH_EDGE hole)",
          any(e.from_node.name == "__START__" and e.to_node.name == "read_graph"
              for e in wf.graph.edges) or
          any(e.to_node.name == "read_graph" for e in wf.graph.edges))
    from bqgraph.queries import _bq, DATASET
    p = _bq().project
    graphs = [r.property_graph_name for r in _bq().query(
        f"SELECT property_graph_name FROM `{p}.{DATASET}`.INFORMATION_SCHEMA.PROPERTY_GRAPHS"
    ).result()]
    check("taste_graph exists (the DDL ran)", "taste_graph" in graphs, str(graphs))
    me = st()["creds"]["creator_id"]
    n = next(iter(_bq().query(
        f"SELECT COUNT(*) c FROM `{p}.{DATASET}.watched` w "
        f"JOIN `{p}.{DATASET}.videos` v ON v.id=w.video_id "
        f"WHERE v.creator_id='{me}'").result())).c
    check("YOUR first-party rows are aligned into the graph", n >= 24, str(n))
    from bqgraph import queries
    rows, engine = queries.taste_neighbors(me)
    check("the graph answers about YOU (taste neighbors)", len(rows) >= 1)
    print(f"    engine: {engine}" + ("" if engine == "gql"
          else " — GQL fell back (edition wall); same rows via the SQL twin"))


def gate_memory():
    from agent.graph import wf
    check("read_memory is WIRED into the fan-out (the MEMORY_EDGE hole)",
          any(e.to_node.name == "read_memory" for e in wf.graph.edges))
    from agent import memory
    check("the bank is provisioned (runs/memorybank.json)",
          (config.RUNS / "memorybank.json").exists())
    facts = memory.recall()
    check("3 notes retrievable from Memory Bank", len(facts) == 3, str(len(facts)))
    joined = " | ".join(m["fact"] for m in facts)
    check("the lesson carries a real number", "%" in joined)
    check("the RULE exists (conclusion-first constraint)",
          any(m["topic"] == "CHANNEL_CONSTRAINTS" for m in facts))
    leaks = [b for b in ("job_", "run_1", "watched_ms", "v_") if b in joined]
    check("ABSENCE: memory holds notes, never readings or ids", not leaks, str(leaks))
    check("consolidation flags recorded", bool(st().get("last_learn_flags")))


def gate_loop():
    s = st()
    lin = s["lineage"]
    check("this is a later lap", s["lap"] >= 2, str(s.get("lap")))
    check("published", "published" in s)
    check("memory citations in the lineage", len(lin["memory_refs"]) >= 1)
    check("graph citations in the lineage", len(lin["graph_refs"]) >= 1)
    valid = {f"memory#{m['ref']}" for m in s.get("memory_facts", [])}
    cited = [e["source"] for e in lin["evidence"] if e["source"].startswith("memory#")]
    check("every cited memory EXISTS in the bank", all(c in valid for c in cited))
    check("the script obeyed the constraint (conclusion_first)",
          lin["hook"]["conclusion_first"] is True)
    check("the idle card could SUGGEST a topic (user:prefs carries one)",
          bool(s.get("prefs", {}).get("last_direction")), str(s.get("prefs")))


GATES = {"spinup": gate_spinup, "one": gate_one, "pending": gate_pending, "workflow": gate_workflow,
         "hitl": gate_hitl, "publish": gate_publish, "state": gate_state,
         "graph": gate_graph, "memory": gate_memory, "loop": gate_loop}
# section aliases - one command per codelab section
ALIASES = {"lap": ["workflow", "hitl", "pending", "publish"],
           "channel": ["memory", "loop"]}

arg = sys.argv[1] if len(sys.argv) > 1 else ""
names = ([arg] if arg in GATES else
         ALIASES.get(arg) or (list(GATES) if arg == "all" else None))
if not names:
    print(f"usage: python -m checks.check <gate|all>   gates: {' · '.join(GATES)}"
          f"   aliases: {' · '.join(ALIASES)}")
    sys.exit(2)
for name in names:
    print(f"── check · {name} ──")
    GATES[name]()
    print()
label = "/".join(names) if len(names) < 3 else "ALL GATES"
if failures:
    print(f"{label}: {len(failures)} FAILURE(S) - see above"); sys.exit(1)
print(f"{label}: GREEN ✓")
