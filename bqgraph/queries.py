"""The measuring instrument: three measurements over taste_graph.

  q1 drop_report       - scalar: where do I lose people? (plain SQL is enough)
  q2 taste_neighbors   - 2-hop: who shares my finishers? (GQL MATCH)
  q3 cocompletion      - 3-hop: what else do my finishers finish? (GQL MATCH)

Each GQL query has a same-shape SQL twin (the diff IS the lesson). Engine order:
GQL -> SQL fallback -> offline note. research_report() feeds the audience_graph
research node; every row set is deterministic so lineage citations can re-run.
"""
import os
import pathlib
import sys

from agent import config as _cfg
DATASET = _cfg.DATASET
# k-anonymity floor: aggregate readings only surface cohorts of >= K viewers.
# (K=2 fits the tiny POC world; a real platform uses K~10+. The queries NEVER
# return viewer ids - this floor also hides "cohort of one" identities.)
K_ANON = int(os.environ.get("STUDIO_K_ANON", "2"))
_client = None


def _bq():
    global _client
    if _client is None:
        from google.cloud import bigquery
        _client = bigquery.Client()
    return _client


def _rows(sql: str) -> list[dict]:
    return [dict(r) for r in _bq().query(sql).result()]


GQL_TASTE_NEIGHBORS = """
SELECT peer_handle, shared_finishers FROM GRAPH_TABLE(`{p}.{d}.taste_graph`
  MATCH (me:creators)-[:published]->(v:videos)<-[w1:watched]-(p:viewers)
        -[w2:watched]->(v2:videos)<-[:published]-(peer:creators)
  WHERE me.id = '{me}' AND w1.completed AND w2.completed AND peer.id <> me.id
  RETURN peer.handle AS peer_handle, COUNT(DISTINCT p.id) AS shared_finishers
) WHERE shared_finishers >= {k}
ORDER BY shared_finishers DESC, peer_handle LIMIT 5
"""

SQL_TASTE_NEIGHBORS = """
SELECT c2.handle AS peer_handle, COUNT(DISTINCT w2.viewer_id) AS shared_finishers
FROM `{p}.{d}.videos` v
JOIN `{p}.{d}.watched` w1 ON w1.video_id = v.id AND w1.completed
JOIN `{p}.{d}.watched` w2 ON w2.viewer_id = w1.viewer_id AND w2.completed
JOIN `{p}.{d}.videos` v2 ON v2.id = w2.video_id AND v2.creator_id != '{me}'
JOIN `{p}.{d}.creators` c2 ON c2.id = v2.creator_id
WHERE v.creator_id = '{me}'
GROUP BY peer_handle HAVING shared_finishers >= {k}
ORDER BY shared_finishers DESC, peer_handle LIMIT 5
"""

GQL_COCOMPLETION = """
SELECT topic_name, fans FROM GRAPH_TABLE(`{p}.{d}.taste_graph`
  MATCH (me:creators)-[:published]->(v:videos)<-[w1:watched]-(p:viewers)
        -[w2:watched]->(v2:videos)-[:about]->(t:topics)
  WHERE me.id = '{me}' AND w1.completed AND w2.completed AND v2.id <> v.id
  RETURN t.name AS topic_name, COUNT(DISTINCT p.id) AS fans
) WHERE fans >= {k}
ORDER BY fans DESC, topic_name LIMIT 5
"""

SQL_COCOMPLETION = """
SELECT t.name AS topic_name, COUNT(DISTINCT w2.viewer_id) AS fans
FROM `{p}.{d}.videos` v
JOIN `{p}.{d}.watched` w1 ON w1.video_id = v.id AND w1.completed
JOIN `{p}.{d}.watched` w2 ON w2.viewer_id = w1.viewer_id AND w2.completed
                          AND w2.video_id != v.id
JOIN `{p}.{d}.about` a ON a.video_id = w2.video_id
JOIN `{p}.{d}.topics` t ON t.id = a.topic_id
WHERE v.creator_id = '{me}'
GROUP BY topic_name HAVING fans >= {k}
ORDER BY fans DESC, topic_name LIMIT 5
"""

SQL_DROP_REPORT = """
SELECT v.id AS video_id, v.title,
       ROUND(AVG(w.watched_ms / v.duration_ms) * 100, 1) AS avg_watch_pct,
       APPROX_QUANTILES(w.drop_ms, 2)[OFFSET(1)] AS median_drop_ms,
       ROUND(COUNTIF(w.drop_ms IS NOT NULL) / COUNT(*) * 100, 1) AS dropped_pct
FROM `{p}.{d}.videos` v JOIN `{p}.{d}.watched` w ON w.video_id = v.id
WHERE v.creator_id = '{me}'
GROUP BY video_id, title, v.duration_ms ORDER BY video_id
"""


def _run(gql: str, sql: str, me: str) -> tuple[list[dict], str]:
    p = _bq().project
    try:
        return _rows(gql.format(p=p, d=DATASET, me=me, k=K_ANON)), "gql"
    except Exception as e:  # Pre-GA surface: fall back to the SQL twin
        print(f"  [bqgraph] GQL failed ({str(e)[:90]}) -> SQL twin", file=sys.stderr)
        return _rows(sql.format(p=p, d=DATASET, me=me, k=K_ANON)), "sql"


def taste_neighbors(me: str):
    return _run(GQL_TASTE_NEIGHBORS, SQL_TASTE_NEIGHBORS, me)


def cocompletion(me: str):
    if GQL_COCOMPLETION is None:
        raise NotImplementedError("TODO: GQL_COCOMPLETION — paste the GQL block "
                                  "from Codelab Step 8 into bqgraph/queries.py")
    return _run(GQL_COCOMPLETION, SQL_COCOMPLETION, me)


def drop_report(me: str):
    p = _bq().project
    return _rows(SQL_DROP_REPORT.format(p=p, d=DATASET, me=me)), "sql"


def _me() -> str | None:
    sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))
    from agent import state
    st = state.load()
    return (st.get("creds") or {}).get("creator_id")


def research_report() -> dict:
    """The audience_graph research node's payload. graph#1..#3 are CITABLE ids."""
    if os.environ.get("STUDIO_NO_BQ"):
        return {"note": "graph offline (STUDIO_NO_BQ)", "queries": []}
    me = _me()
    if not me:
        return {"note": "no creator yet", "queries": []}
    try:
        q1, e1 = drop_report(me)
        q2, e2 = taste_neighbors(me)
        q3, e3 = cocompletion(me)
    except Exception as e:
        return {"note": f"graph unavailable: {str(e)[:120]}", "queries": []}
    report = {"queries": [
        {"id": "graph#1", "question": "where do I lose people?",
         "engine": e1, "rows": q1},
        {"id": "graph#2", "question": "who shares my finishers?",
         "engine": e2, "rows": q2},
        {"id": "graph#3", "question": "what else do my finishers finish?",
         "engine": e3, "rows": q3},
    ]}
    if not q2 and not q3:
        report["note"] = ("the graph EXISTS but cannot find you yet - "
                         "no completed views of your videos are in it")
    return report


if __name__ == "__main__":
    import json
    print(json.dumps(research_report(), indent=1))
