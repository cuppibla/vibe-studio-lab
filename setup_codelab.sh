#!/usr/bin/env bash
# Vibe Studio — one-shot environment setup for the CODELAB (uv path).
# Safe to re-run any number of times.
#
# Run ./setup_project.sh FIRST: this script reads the project it recorded in
# ~/project_id.txt. It leaves you with:
#   • uv installed, a .venv, and exactly what uv.lock pins inside it
#   • the two APIs this lab actually calls, enabled on that project
#   • a .env that sends every model call to Vertex AI with your own creds
#   • one real Gemini call, proven, before any chapter depends on it
#
# It asks exactly two questions — the room's event code and the name the room
# credits you by — and both take the default on a plain Enter. Everything else
# is non-interactive, and with no tty attached both questions take the default
# too, so this is safe from a script or a container.
#
# What it deliberately does NOT do: create the Memory Bank Agent Engine
# resource. Enabling aiplatform.googleapis.com is the right boundary — the 🧠
# chapter has you press "Connect the bank ▸" yourself, and pre-creating the
# resource would spoil that chapter.
set -euo pipefail
cd "$(dirname "$0")"

say()  { printf '\n\033[1m%s\033[0m\n' "$1"; }
tick() { printf '  ✓ %s\n' "$1"; }
info() { printf '  · %s\n' "$1"; }
warn() { printf '  ! %s\n' "$1" >&2; }

# Print a block of guidance and stop. Never waits for input.
die() {
    printf '\n\033[1m✗ %s\033[0m\n\n' "$1" >&2
    shift
    for line in "$@"; do printf '%s\n' "$line" >&2; done
    printf '\n' >&2
    exit 1
}

say "Vibe Studio · setup"

# ── 1 · python env + deps (uv owns both) ────────────────────────────────────
# uv is the only dependency path: `uv venv` makes .venv, `uv sync` installs
# exactly what uv.lock pins. Nothing is pip-installed on the side.
UV_WAS_INSTALLED=0
if ! command -v uv >/dev/null 2>&1; then
    info "uv not found — installing it from astral.sh"
    curl -LsSf https://astral.sh/uv/install.sh | sh >/dev/null 2>&1 || die \
        "Could not install uv." \
        "Install it by hand, then re-run ./setup_codelab.sh:" \
        "  curl -LsSf https://astral.sh/uv/install.sh | sh" \
        "  source ~/.local/bin/env"
    # The installer drops uv in ~/.local/bin and writes an env file for it.
    if [ -f "$HOME/.local/bin/env" ]; then
        set +u
        # shellcheck disable=SC1091
        . "$HOME/.local/bin/env"
        set -u
    fi
    export PATH="$HOME/.local/bin:$PATH"
    UV_WAS_INSTALLED=1
fi
command -v uv >/dev/null 2>&1 || die \
    "uv installed but is not on PATH." \
    "Put it there, then re-run ./setup_codelab.sh:" \
    "  source ~/.local/bin/env"
tick "uv $(uv --version 2>/dev/null | awk '{print $2}')"

uv venv
uv sync
[ -x .venv/bin/python ] || die \
    "uv sync finished but .venv/bin/python is missing." \
    "Clear the env and let uv rebuild it:" \
    "  rm -rf .venv && ./setup_codelab.sh"
tick "uv env + google-adk[db]==2.5.0 (locked) — activate it with: source .venv/bin/activate"

# ── 2 · the project, and only the APIs this lab calls ───────────────────────
say "1 · APIs"

PROJECT=""
PROJECT_FILE="$HOME/project_id.txt"
if [ -f "$PROJECT_FILE" ]; then
    PROJECT="$(tr -d '[:space:]' < "$PROJECT_FILE" || true)"
    [ -n "$PROJECT" ] && info "project: $PROJECT (from $PROJECT_FILE)"
fi
if [ -z "$PROJECT" ]; then
    PROJECT="$(gcloud config get-value project 2>/dev/null || true)"
    [ -n "$PROJECT" ] && info "project: $PROJECT (from gcloud config)"
fi
[ -n "$PROJECT" ] || die \
    "No Google Cloud project to point at." \
    "This script reads the project ./setup_project.sh records. Run that first:" \
    "" \
    "  ./setup_project.sh" \
    "" \
    "Already have a project? Tell this lab about it and re-run:" \
    "  echo YOUR_PROJECT_ID > ~/project_id.txt" \
    "  gcloud config set project YOUR_PROJECT_ID"

gcloud config set project "$PROJECT" -q >/dev/null 2>&1 || true

# Two APIs, and nothing else. aiplatform serves three of this lab's calls
# (Gemini, Veo, and the Memory Bank the 🧠 chapter connects); bigquery serves
# the world graph the 🌍 chapter builds. Anything else would be enabling a
# product this lab never touches.
enable_api() {
    local api="$1" what="$2"
    gcloud services enable "$api" --project="$PROJECT" -q 2>/dev/null || die \
        "Could not enable $api on $PROJECT." \
        "Usually this means billing is not on the project yet, or the project" \
        "is seconds old and its IAM policy is still propagating." \
        "" \
        "Wait a minute, then re-run:" \
        "" \
        "  ./setup_project.sh    # confirms billing, waits for the project" \
        "  ./setup_codelab.sh"
    tick "$api  ($what)"
}
enable_api aiplatform.googleapis.com "Gemini · Veo · Memory Bank"
enable_api bigquery.googleapis.com   "the world graph"

# ── 3 · the room — the only two questions in either script ──────────────────
say "2 · The room"

# Read what a previous run wrote so a second run never clobbers an event code
# the attendee already chose: the old value becomes the offered default.
env_get() {
    [ -f .env ] || return 0
    grep -s "^$1=" .env | tail -1 | cut -d= -f2- || true
}

# ask <prompt> <default>  → answer on stdout.
# bash sends `read -p`'s prompt to stderr, so command substitution here still
# captures only the answer. No tty (piped, CI, container) → take the default
# rather than block forever on a read that can never be answered.
ask() {
    local prompt="$1" default="$2" reply=""
    if [ -t 0 ]; then
        read -r -p "  $prompt [$default]: " reply || reply=""
    else
        printf '  · no tty — %s takes the default (%s)\n' "$prompt" "$default" >&2
    fi
    reply="$(printf '%s' "${reply:-$default}" | sed -e 's/^[[:space:]]*//' -e 's/[[:space:]]*$//')"
    printf '%s' "${reply:-$default}"
}

EVENT_DEFAULT="$(env_get VIBETUBE_EVENT)"
[ -n "$EVENT_DEFAULT" ] || EVENT_DEFAULT="sandbox"

NAME_DEFAULT="$(env_get VIBETUBE_NAME)"
if [ -z "$NAME_DEFAULT" ]; then
    # The local part of the signed-in gcloud account, tidied into a name:
    # "annie.wang@example.com" → "Annie Wang".
    ACCOUNT="$(gcloud config get-value account 2>/dev/null || true)"
    NAME_DEFAULT="$(printf '%s' "${ACCOUNT%%@*}" \
        | tr '._-' '   ' \
        | awk '{for (i = 1; i <= NF; i++) $i = toupper(substr($i, 1, 1)) substr($i, 2); print}')"
    [ -n "$NAME_DEFAULT" ] || NAME_DEFAULT="Anonymous Creator"
fi

info "press Enter to take the [default] — both answers live in .env, editable later"
VIBETUBE_EVENT="$(ask 'Room event code' "$EVENT_DEFAULT")"
VIBETUBE_NAME="$(ask 'Name the room credits you by' "$NAME_DEFAULT")"
tick "room: $VIBETUBE_EVENT · credited as \"$VIBETUBE_NAME\""

# ── 4 · .env, written whole ─────────────────────────────────────────────────
# Written whole, never appended: a second run can no more duplicate a line
# than it can lose the answers above, because both were read back first.
say "3 · .env"

if [ -f .env ]; then
    cp .env .env.bak
    info "previous .env saved as .env.bak"
fi

{
    echo "# Written by ./setup_codelab.sh — safe to edit, safe to re-run."
    echo ""
    echo "# ── auth: Cloud Shell / Vertex via ADC (no keys) ──"
    echo "STUDIO_VERTEX=1"
    echo "GOOGLE_CLOUD_PROJECT=$PROJECT"
    echo ""
    echo "# ── three services, three locations. They are NOT interchangeable. ──"
    echo "# 1 · Gemini → global. Not a region: Gemini here runs on dynamic shared"
    echo "#     quota, so one busy region can 429 through no fault of yours."
    echo "#     global draws on capacity across regions instead. (agent/config.py)"
    echo "GOOGLE_CLOUD_LOCATION=global"
    echo "# 2 · Veo → us-central1. Video generation is REGIONAL and has no global"
    echo "#     endpoint at all: asking global for it returns 404 Publisher Model"
    echo "#     not found. Do not 'fix' this to match the line above. (world/broker.py)"
    echo "STUDIO_VEO_MODEL=veo-3.1-fast-generate-001"
    echo "STUDIO_VEO_LOCATION=us-central1"
    echo "# 3 · Memory Bank → us-central1. Agent Engine is regional too, and it"
    echo "#     reads its own variable, not the one above. (agent/memory.py)"
    echo "GOOGLE_CLOUD_LOCATION_MB=us-central1"
    echo ""
    echo "# ── the render farm: real Veo, not the prebaked clock ──"
    echo "STUDIO_REAL_VIDEO=1"
    echo ""
    echo "# ── the world graph ──"
    echo "STUDIO_DATASET=vibestudio"
    echo ""
    echo "# ── the room's shared platform ──"
    echo "VIBETUBE_URL=https://vibetube.dev"
    echo "VIBETUBE_EVENT=$VIBETUBE_EVENT"
    echo "VIBETUBE_NAME=$VIBETUBE_NAME"
} > .env.tmp
mv .env.tmp .env
tick "wrote .env — Vertex via ADC on $PROJECT, no API key anywhere"
tick "Gemini → global · Veo → us-central1 · Memory Bank → us-central1"

# Veo is regional and this lab renders for real, so prove the model is served
# in the region .env just named. This is the publisher-model metadata GET: it
# reads the catalogue, it starts no render, and it costs nothing.
VEO_TOKEN="$(gcloud auth print-access-token 2>/dev/null || true)"
VEO_STATUS="$(curl -s -o /dev/null -w '%{http_code}' --max-time 15 \
    -H "Authorization: Bearer $VEO_TOKEN" \
    -H "x-goog-user-project: $PROJECT" \
    "https://us-central1-aiplatform.googleapis.com/v1/publishers/google/models/veo-3.1-fast-generate-001" \
    2>/dev/null || echo 000)"
if [ "$VEO_STATUS" = "200" ]; then
    tick "real Veo on: veo-3.1-fast-generate-001 is served in us-central1 — renders take real minutes and spend real credit"
else
    warn "Veo did not confirm in us-central1 (HTTP $VEO_STATUS)."
    warn "Renders may fall back to the prebaked clock. To run cost-free on"
    warn "purpose, set STUDIO_REAL_VIDEO=0 in .env."
fi

# scripts/preflight.py probes the room whenever URL and EVENT are both set, so
# a configured-but-unreachable room is a ✗ there. Find that out here instead.
ROOM_STATUS="$(curl -s -o /dev/null -w '%{http_code}' --max-time 5 \
    "https://vibetube.dev/api/events/$VIBETUBE_EVENT" 2>/dev/null || echo 000)"
if [ "$ROOM_STATUS" = "200" ]; then
    tick "room reachable: https://vibetube.dev/api/events/$VIBETUBE_EVENT"
else
    warn "the room did not answer (HTTP $ROOM_STATUS) — preflight will show"
    warn "  ✗ room: connected ($VIBETUBE_EVENT)"
    warn "Nothing else in the lab needs it. To go local-only, blank the line"
    warn "in .env:  VIBETUBE_EVENT=   — then re-run preflight."
fi

# ── 5 · prove the model answers ─────────────────────────────────────────────
say "4 · Live model call"

uv run python - <<'PY'
import os

from dotenv import load_dotenv

load_dotenv(".env", override=True)
# Same rule as agent/config.py: STUDIO_VERTEX=1 means "Vertex AI via ADC".
if os.environ.get("STUDIO_VERTEX", "").lower() in ("1", "true"):
    os.environ["GOOGLE_GENAI_USE_VERTEXAI"] = "True"
    os.environ.pop("GOOGLE_API_KEY", None)

from google import genai
from google.genai import types as gt

client = genai.Client()
r = client.models.generate_content(
    model="gemini-2.5-flash",
    contents="Reply with exactly: vibe studio, ready to roll.",
    config=gt.GenerateContentConfig(
        thinking_config=gt.ThinkingConfig(thinking_budget=0), temperature=0.0))
print("  ✓ gemini-2.5-flash:", (r.text or "").strip())
PY

say "Setup finished."
if [ "$UV_WAS_INSTALLED" -eq 1 ]; then
    info "uv was just installed — run 'source ~/.local/bin/env' to get it in this shell"
fi
printf '  Next:  source .venv/bin/activate && python scripts/preflight.py\n\n'
