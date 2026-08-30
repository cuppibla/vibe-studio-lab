# Long-Running Workflows & Durable State with ADK

The starter repo for the **Vibe Studio** codelab: you run a video channel
whose agent has to wait well — renders take minutes, humans take longer,
audiences answer tomorrow.

The full walkthrough lives in [`CODELAB.md`](CODELAB.md). Everything here
ships complete except **three one-line edits** you make while following it.

## What it teaches

| | |
|---|---|
| ⏳ 📬 | **long running** — `pending` is a value in the session log, not a thread; resume is one `function_response` with the same call id |
| 🔺 🗺️ 🏁 | **workflows + human-in-the-loop** — three runnable shapes (line · router · fan-out+join), nodes sharing one state, an agent as a node and a workflow as a node; then the real graph, where `RequestInput` pauses it for a person |
| 💾 | **session state** — `Event(state=…)` → `session.state` → the SessionService, and what the `user:` prefix changes |
| 🌍 | **BigQuery property graph** — a declared lens over tables you already have |
| 🧠 | **Memory Bank** — connect a managed bank, write distilled notes, and read them back inside the agent's research step |

## Run it

```bash
git clone https://github.com/cuppibla/vibe-studio-lab
cd vibe-studio-lab
uv sync
source .venv/bin/activate
cp .env.example .env
python scripts/preflight.py
```

Then open [`CODELAB.md`](CODELAB.md) and follow it — it boots each surface
(`adk web`, the Vibe Studio app) right before the first step that needs it.

Google Cloud is optional for the first half; chapters 🌍 and 🧠 need a
project with BigQuery and Vertex AI enabled (Cloud Shell already has
credentials). `STUDIO_NO_BQ=1` / `STUDIO_NO_MB=1` degrade those chapters
honestly if you want to skip them.

## Repo map

```
agent/       the backend you read (and lightly edit): the workflow, the desk,
             drivers (deliver · finish · learn · bank · premiere)
vibestudio/  8-line adk web entry — exports root_agent
shape1_line/ shape2_router/ shape3_fanout/
             chapter 🔺 — three sandbox workflows, each its own adk web app
app/         Vibe Studio: the frontend + the Wall API, one FastAPI server
world/       the prebaked render farm, the platform, the thumbnail generator
bqgraph/     chapter 🌍 — load · export · report over a BigQuery property graph
checks/      verification gates (`python -m checks.check <name>`) + the hole registry
scripts/     preflight · graph.sh · carve · rescue · reset · shape_maps
solutions/   the filled reference tree the verifiers diff against
CODELAB.md   the lab itself
```

## For authors

The three student edits are carved from the reference tree by
`scripts/carve.py` (see `SHIP_HOLES`); `scripts/rescue.py` fills them back
in — handy if you want a fully working tree for screenshots:

```bash
python scripts/rescue.py        # fill every hole
python scripts/carve.py         # back to the shipped starter
python -m checks.verify_holes   # carve + registry == solutions, byte for byte
python -m checks.verify_pastes  # every code block in CODELAB.md matches too
```

Diagram sources (hand-authored SVG) live in `codelab-img/src/`.
