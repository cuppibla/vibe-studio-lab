"""Connect your Radar subscription: load the vendor's industry pack (channels,
videos, topics + the opt-in pseudonymous PANEL of 200 viewers - the Nielsen/
qiangua mechanism) into YOUR BigQuery dataset, and create the property graph.
Run: uv run python -m bqgraph.load    (or Studio -> Audience -> Connect)"""
import pathlib

from google.cloud import bigquery

HERE = pathlib.Path(__file__).resolve().parent
SEED = HERE / "../world/seeds"
from agent import config as _cfg
DATASET = _cfg.DATASET

SCHEMAS = {
    "creators": [("id", "STRING"), ("handle", "STRING"), ("cluster", "STRING")],
    "topics": [("id", "STRING"), ("name", "STRING"), ("cluster", "STRING")],
    "videos": [("id", "STRING"), ("creator_id", "STRING"), ("title", "STRING"),
               ("duration_ms", "INT64")],
    "about": [("video_id", "STRING"), ("topic_id", "STRING")],
    "viewers": [("id", "STRING"), ("cluster", "STRING")],
    "watched": [("viewer_id", "STRING"), ("video_id", "STRING"), ("watched_ms", "INT64"),
                ("drop_ms", "INT64"), ("completed", "BOOL"), ("is_synthetic", "BOOL")],
}

GRAPH_DDL = """
CREATE OR REPLACE PROPERTY GRAPH `{p}.{d}.taste_graph`
  NODE TABLES (
    `{d}.creators` AS creators KEY (id),
    `{d}.videos` AS videos KEY (id),
    `{d}.viewers` AS viewers KEY (id),
    `{d}.topics` AS topics KEY (id)
  )
  EDGE TABLES (
    `{d}.videos` AS published
      KEY (id)
      SOURCE KEY (creator_id) REFERENCES creators (id)
      DESTINATION KEY (id) REFERENCES videos (id),
    `{d}.about` AS about
      KEY (video_id, topic_id)
      SOURCE KEY (video_id) REFERENCES videos (id)
      DESTINATION KEY (topic_id) REFERENCES topics (id),
    `{d}.watched` AS watched
      KEY (viewer_id, video_id)
      SOURCE KEY (viewer_id) REFERENCES viewers (id)
      DESTINATION KEY (video_id) REFERENCES videos (id)
  )
"""


def main():
    client = bigquery.Client()
    proj = client.project
    client.create_dataset(f"{proj}.{DATASET}", exists_ok=True)
    print(f"dataset {proj}.{DATASET} ready")

    for table, cols in SCHEMAS.items():
        schema = [bigquery.SchemaField(n, t) for n, t in cols]
        job = client.load_table_from_file(
            open(SEED / f"{table}.csv", "rb"),
            f"{proj}.{DATASET}.{table}",
            job_config=bigquery.LoadJobConfig(
                schema=schema, skip_leading_rows=1,
                write_disposition="WRITE_TRUNCATE", source_format="CSV",
                allow_quoted_newlines=True, null_marker=""))
        job.result()
        n = client.get_table(f"{proj}.{DATASET}.{table}").num_rows
        print(f"  {table}: {n} rows")

    print("creating property graph (Pre-GA) ...")
    if "TODO: EDGE_TABLE" in GRAPH_DDL:
        raise NotImplementedError("TODO: EDGE_TABLE — paste the EDGE TABLES "
                                  "block from Codelab Step 7 into bqgraph/load.py")
    client.query(GRAPH_DDL.format(p=proj, d=DATASET)).result()
    print("  taste_graph created ✓")

    import json
    import time
    runs = HERE.parent / "runs"
    runs.mkdir(exist_ok=True)
    (runs / "radar.json").write_text(json.dumps({"connected": True, "at": time.time()}))
    print("Radar subscription connected (industry pack + panel in YOUR dataset)")


if __name__ == "__main__":
    main()
