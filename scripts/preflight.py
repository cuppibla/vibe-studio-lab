"""One command, all the ticks - run this before the lab starts.
Run: python scripts/preflight.py [--ping]   (--ping spends one tiny model call)"""
import os
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

ok = True


def tick(name, cond, hint=""):
    global ok
    print(("  ✓ " if cond else "  ✗ ") + name + ("" if cond else f"   → {hint}"))
    ok = ok and bool(cond)


v = sys.version_info
tick(f"python {v.major}.{v.minor}", (3, 12) <= (v.major, v.minor) < (3, 13),
     "use the repo venv: uv sync && source .venv/bin/activate")
try:
    import greenlet  # noqa: F401
    tick("greenlet (async sqlite)", True)
except ImportError:
    tick("greenlet (async sqlite)", False, "uv sync")

from agent import config  # noqa: E402
if os.environ.get("STUDIO_VERTEX"):
    tick("auth path A: Vertex via ADC (STUDIO_VERTEX=1)", True)
else:
    tick("auth path B: GOOGLE_API_KEY set", bool(os.environ.get("GOOGLE_API_KEY")),
         "cp .env.example .env — path A (Cloud Shell) or paste an AI Studio key")

if "--ping" in sys.argv:
    try:
        from google import genai
        r = genai.Client(api_key=os.environ["GOOGLE_API_KEY"]).models.generate_content(
            model=config.MODEL, contents="reply exactly: OK")
        tick(f"model ping ({config.MODEL})", "OK" in (r.text or ""), "check the key")
    except Exception as e:
        tick(f"model ping ({config.MODEL})", False, str(e)[:70])

no_bq, no_mb = os.environ.get("STUDIO_NO_BQ"), os.environ.get("STUDIO_NO_MB")
if no_bq:
    print("  - BigQuery: skipped (STUDIO_NO_BQ=1 — graph readings degrade honestly)")
else:
    try:
        from google.cloud import bigquery
        c = bigquery.Client()
        tick(f"Google Cloud ADC (project {c.project})", True)
    except Exception as e:
        tick("Google Cloud ADC", False,
             f"gcloud auth application-default login   ({str(e)[:50]})")
if no_mb:
    print("  - Memory Bank: skipped (STUDIO_NO_MB=1 — notes fall back to empty)")
else:
    try:
        import vertexai  # noqa: F401
        tick("Memory Bank SDK", True)
    except ImportError:
        tick("Memory Bank SDK", False, "uv sync")

# the five stage apps the workflow act grows through - adk web lists them
for app in ("stage0_prompt", "stage1_fanout", "stage2_pause",
            "stage3_script", "stage4_gates"):
    try:
        mod = __import__(f"{app}.agent", fromlist=["root_agent"])
        n = getattr(getattr(mod.root_agent, "graph", None), "edges", None)
        label = f"{app} loads" + (f" ({len(n)} edges)" if n is not None else "")
        tick(label, True)
    except Exception as e:
        tick(f"{app} loads", False, str(e)[:70])

try:
    import httpx
    r = httpx.get(f"{config.STUDIO_URL}/api/trends", timeout=3)
    tick(f"Vibe Studio up at {config.STUDIO_URL}", r.status_code == 200)
except Exception:
    # not a failure: the studio is deliberately booted in section 2,
    # right before the first click that needs it
    print(f"  - Vibe Studio: not running yet (section 2 boots it)")

# the room: optional. Configured -> reachable is a tick; blank -> local only.
room_url = os.environ.get("VIBETUBE_URL", "").rstrip("/")
room_event = os.environ.get("VIBETUBE_EVENT", "").strip()
if room_url and room_event:
    try:
        import httpx
        r = httpx.get(f"{room_url}/api/events/{room_event}", timeout=5)
        tick(f"room: connected ({room_event})", r.status_code == 200,
             f"platform said {r.status_code} — check VIBETUBE_URL/EVENT")
    except Exception as e:
        tick(f"room: connected ({room_event})", False, str(e)[:70])
else:
    print("  - room: not configured (local only — publishing still works)")

print("\nPREFLIGHT " + ("GREEN" if ok else "NOT READY - fix the ✗ lines above"))
sys.exit(0 if ok else 1)
