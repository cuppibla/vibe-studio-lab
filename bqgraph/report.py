"""`python -m bqgraph.report` - the two readings, in your terminal.
Same queries the research node runs; graph#N ids are what briefs cite."""
from agent import state

from . import queries


def main():
    st = state.load()
    me = (st.get("creds") or {}).get("creator_id")
    if not me:
        print("no creator yet — run a lap first"); return
    q1, e1 = queries.drop_report(me)
    print("graph#1 · where do I lose people?            engine:", e1)
    for r in q1:
        print(f"   {r['title'][:44]:44} avg {r['avg_watch_pct']:>5}% · "
              f"median drop {r['median_drop_ms']} ms · dropped {r['dropped_pct']}%")
    q3, e3 = queries.cocompletion(me)
    print("graph#3 · what else do my finishers finish?  engine:", e3)
    for r in q3:
        print(f"   {r['topic_name'][:44]:44} fans {r['fans']}")


if __name__ == "__main__":
    main()
