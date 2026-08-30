"""`python -m bqgraph.report` - the readings, in your terminal AND in the app.

Runs exactly what the research node runs, prints it, and writes
runs/graph_report.json so Vibe Studio's World tab can show the same rows
without touching BigQuery in a web request."""
import json

from agent import config, state  # noqa: F401  (state import keeps the CWD contract)

from . import queries

LINE = {
    "graph#1": lambda r: (f"   {r['title'][:44]:44} avg {r['avg_watch_pct']:>5}% · "
                          f"median drop {r['median_drop_ms']} ms · dropped {r['dropped_pct']}%"),
    "graph#2": lambda r: f"   {r['peer_handle'][:44]:44} shared finishers {r['shared_finishers']}",
    "graph#3": lambda r: f"   {r['topic_name'][:44]:44} fans {r['fans']}",
}


def main():
    rep = queries.research_report()
    config.RUNS.mkdir(exist_ok=True)
    (config.RUNS / "graph_report.json").write_text(json.dumps(rep, indent=1))
    if rep.get("note"):
        print(rep["note"])
    for q in rep["queries"]:
        print(f"{q['id']} · {q['question']:<38} engine: {q['engine']}")
        for row in q["rows"]:
            print(LINE[q["id"]](row))


if __name__ == "__main__":
    main()
