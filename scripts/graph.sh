#!/usr/bin/env bash
# The whole BigQuery section, three verbs, one command:
#   1/3 CONNECT+LOAD  bqgraph/load.py    dataset + vendor pack + the graph DDL
#   2/3 STORE         bqgraph/export.py  YOUR wall rows -> graph rows (idempotent)
#   3/3 READ          bqgraph/report.py  the two readings the research node uses
set -e
cd "$(dirname "$0")/.."

echo "══ 1/3 CONNECT + LOAD ══ (bqgraph/load.py)"
python -m bqgraph.load

echo
echo "══ 2/3 STORE ══ (bqgraph/export.py — your rows enter the world)"
python -m bqgraph.export

echo
echo "══ 3/3 READ ══ (bqgraph/report.py — the readings briefs will cite)"
python -m bqgraph.report
