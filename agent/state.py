"""Driver state (runs/state.json) - the app-level working memory.
Session events are ADK's log; this file is the conductor's clipboard."""
import json

from . import config


def load() -> dict:
    if config.STATE.exists():
        return json.loads(config.STATE.read_text())
    return {}


def save(st: dict) -> None:
    config.STATE.write_text(json.dumps(st, indent=2, ensure_ascii=False))


def update(**kw) -> dict:
    st = load()
    st.update(kw)
    save(st)
    return st
