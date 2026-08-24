"""`python -m agent.learn` - the after-audience job (run it once viewers watched).

outcomes + graph readings -> the outcome->RULE step (deterministic distillation,
in code where the learner can read it) -> Memory Bank -> action flags printed.

Steering wheel:
  python -m agent.learn --forget <memory_id>
  python -m agent.learn --inject "[CHANNEL_CONSTRAINTS] ..."
"""
import sys

from . import memory, state


def distill() -> list[str]:
    from bqgraph import queries
    st = state.load()
    me = st["creds"]["creator_id"]

    drops, _ = queries.drop_report(me)
    neighbors, _ = queries.taste_neighbors(me)
    topics, _ = queries.cocompletion(me)

    facts = []
    pub_id = (st.get("published") or {}).get("video_id")
    latest = next((d for d in drops if d["video_id"] == pub_id), drops[-1] if drops else None)
    if latest and latest["dropped_pct"] >= 40:
        hook_s = st["lineage"]["hook"]["hook_at_ms"] / 1000
        facts.append(
            f"[CHANNEL_LESSONS] Lap {st['lap']} '{latest['title']}' lost "
            f"{latest['dropped_pct']:.0f}% of viewers (avg watch "
            f"{latest['avg_watch_pct']:.0f}%); the hook arrived at {hook_s:.0f}s.")
        # the outcome -> RULE step: a retention number becomes a checkable behavior
        facts.append("[CHANNEL_CONSTRAINTS] Open with the conclusion in the "
                     "first 3 seconds.")
    if neighbors:
        top = neighbors[0]
        t = topics[0] if topics else None
        facts.append(
            f"[AUDIENCE] Your finishers overlap most with @{top['peer_handle']} "
            f"({top['shared_finishers']} shared finishers)"
            + (f"; they also finish '{t['topic_name']}' videos "
               f"({t['fans']} fans)." if t else "."))
    return facts


def main():
    if "--forget" in sys.argv:
        mid = sys.argv[sys.argv.index("--forget") + 1]
        memory.forget(mid)
        print(f"forgot memory#{mid}")
        return
    if "--recall" in sys.argv:
        # the READ path, by hand: similarity retrieval from Memory Bank
        q = sys.argv[sys.argv.index("--recall") + 1]
        for m in memory.recall(q):
            print(f"  memory#{m['id'][:8]} [{m['topic']}] {m['fact']}")
        return
    if "--inject" in sys.argv:
        fact = sys.argv[sys.argv.index("--inject") + 1]
        flags = memory.inject(fact)
        print(f"injected: {flags}")
        return

    # the after-audience job does THREE things in one verb -
    # align your first-party data into the Radar graph, take readings, keep notes
    print("── aligning first-party data into the Radar graph ──")
    from bqgraph import export as bq_export
    bq_export.main()

    facts = distill()
    if not facts:
        print("nothing to learn yet (no outcomes)")
        return
    print("distilled (readings -> notes):")
    for f in facts:
        print(f"  {f}")
    flags = memory.write_facts(facts)
    st = state.load()
    st["last_learn_flags"] = flags
    state.save(st)
    print("consolidation flags:")
    for fl in flags:
        print(f"  {fl['action']} memory#{fl['id'][:10]}")
    recalled = memory.recall()
    st = state.load()
    st["memory_facts"] = [{"id": m["id"], "ref": m["id"][:8], "topic": m["topic"],
                           "fact": m["fact"]} for m in recalled]
    state.save(st)
    print(f"memory now holds {len(recalled)} fact(s); state.memory_facts updated")


if __name__ == "__main__":
    main()
