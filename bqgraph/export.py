"""Push YOUR rows into the room graph (outcomes.json -> BQ inserts).
The one INSERT that makes "the graph can find you now" true.
Run: uv run python -m bqgraph.export      (idempotent per creator)
"""
import json
import pathlib
import sys

from google.cloud import bigquery

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))
from agent import config, state  # noqa: E402
from world import platform  # noqa: E402

from agent import config as _cfg
DATASET = _cfg.DATASET

TOPIC_MAP = [("explainer", "t_quick_explainer"), ("edit", "t_editing"),
             ("hook", "t_hooks"), ("retention", "t_hooks"),
             ("one-take", "t_onetake"), ("city", "t_citydata"),
             ("agent", "t_agents")]


def topic_for(title_topic: str) -> str:
    t = title_topic.lower()
    for kw, tid in TOPIC_MAP:
        if kw in t:
            return tid
    return "t_agents"


def main():
    st = state.load()
    creds = st["creds"]
    me = creds["creator_id"]
    vids = platform.outcomes(me)
    if not vids:
        print("no outcomes yet"); return

    client = bigquery.Client()
    p = client.project
    q = lambda sql, **params: client.query(  # noqa: E731
        sql, job_config=bigquery.QueryJobConfig(query_parameters=[
            bigquery.ScalarQueryParameter(k, "STRING", v) for k, v in params.items()
        ])).result()

    # idempotent: wipe my prior rows, then insert fresh
    q(f"DELETE FROM `{p}.{DATASET}.watched` WHERE video_id IN "
      f"(SELECT id FROM `{p}.{DATASET}.videos` WHERE creator_id=@me)", me=me)
    q(f"DELETE FROM `{p}.{DATASET}.about` WHERE video_id IN "
      f"(SELECT id FROM `{p}.{DATASET}.videos` WHERE creator_id=@me)", me=me)
    q(f"DELETE FROM `{p}.{DATASET}.videos` WHERE creator_id=@me", me=me)
    q(f"DELETE FROM `{p}.{DATASET}.creators` WHERE id=@me", me=me)

    rows_creators = [{"id": me, "handle": "annie", "cluster": "quickcut"}]
    rows_videos, rows_about, rows_watched, viewer_ids = [], [], [], set()
    for v in vids:
        rows_videos.append({"id": v["video_id"], "creator_id": me,
                            "title": v["title"], "duration_ms": v["duration_ms"]})
        rows_about.append({"video_id": v["video_id"],
                           "topic_id": topic_for(st["lineage"]["topic"])})
        for r in v["view_rows"]:
            viewer_ids.add(r["viewer_id"])
            rows_watched.append({
                "viewer_id": r["viewer_id"], "video_id": v["video_id"],
                "watched_ms": r["watched_ms"], "drop_ms": r["drop_ms"],
                "completed": bool(r["completed"]), "is_synthetic": bool(r["is_synthetic"])})

    existing = {r.id for r in q(
        f"SELECT id FROM `{p}.{DATASET}.viewers` WHERE id IN UNNEST(@ids)".replace(
            "@ids", "[" + ",".join(f"'{v}'" for v in viewer_ids) + "]"))}
    rows_viewers = [{"id": v, "cluster": "quickcut" if v.startswith("syn_q") else
                     ("slowburn" if v.startswith("syn_s") else "casual")}
                    for v in viewer_ids - existing]

    def sqlval(v):
        if v is None:
            return "NULL"
        if isinstance(v, bool):
            return "TRUE" if v else "FALSE"
        if isinstance(v, (int, float)):
            return str(v)
        return "'" + str(v).replace("\\", "\\\\").replace("'", "\\'") + "'"

    # INSERT via DML (not streaming) so the DELETE-then-INSERT stays idempotent
    for table, rows in [("creators", rows_creators), ("viewers", rows_viewers),
                        ("videos", rows_videos), ("about", rows_about),
                        ("watched", rows_watched)]:
        if rows:
            cols = list(rows[0].keys())
            values = ",".join(
                "(" + ",".join(sqlval(r[c]) for c in cols) + ")" for r in rows)
            client.query(f"INSERT INTO `{p}.{DATASET}.{table}` "
                         f"({','.join(cols)}) VALUES {values}").result()
        print(f"  +{len(rows)} {table}")
    print(f"exported {len(rows_videos)} video(s), {len(rows_watched)} watch edges -> "
          f"the graph can find you now")


if __name__ == "__main__":
    main()
