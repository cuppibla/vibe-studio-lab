"""Channel memory - REAL Memory Bank (Agent Engine, her GCP project via ADC).

recall()  -> the read_memory research node (fresh retrieve every run)
learn()   -> the after-audience run: outcomes + graph readings -> 3 distilled
             facts -> memories.generate (blocking) -> action flags
forget()/inject() -> the steering wheel (governance over evolution)

Facts carry a "[TOPIC] " prefix (CHANNEL_LESSONS / CHANNEL_CONSTRAINTS / AUDIENCE).
Readings never enter memory; notes do (analytics != memory).
"""
import json
import os
import pathlib

from . import config

ENGINE_CACHE = config.RUNS / "memorybank.json"
LOCATION = os.environ.get("GOOGLE_CLOUD_LOCATION_MB", "us-central1")
SCOPE = {"app_name": config.APP, "user_id": config.USER}

_client = None


def project() -> str:
    """YOUR project - the same one BigQuery uses. Set STUDIO_GCP_PROJECT to
    override; otherwise it comes from Application Default Credentials, so a
    plain `gcloud auth application-default login` (or Cloud Shell) is enough."""
    p = os.environ.get("STUDIO_GCP_PROJECT") or os.environ.get("GOOGLE_CLOUD_PROJECT")
    if p:
        return p
    import google.auth
    _, adc_project = google.auth.default()
    if not adc_project:
        raise RuntimeError("no GCP project found - set STUDIO_GCP_PROJECT in .env "
                           "or run: gcloud auth application-default login")
    return adc_project


def _cli():
    global _client
    if _client is None:
        import vertexai
        _client = vertexai.Client(project=project(), location=LOCATION)
    return _client


# The bank's configuration - THE Memory Bank vocabulary, in one place.
# memory_topics tell consolidation what a "note" is allowed to be about:
# our three custom topics mirror the [TOPIC] prefixes distill() writes.
# (Managed topics like USER_PREFERENCES exist too - see ManagedTopicEnum.)
def _bank_config():
    from vertexai._genai import types as vt
    topic = vt.MemoryBankCustomizationConfigMemoryTopic
    custom = vt.MemoryBankCustomizationConfigMemoryTopicCustomMemoryTopic
    return vt.AgentEngineConfig(
        display_name="vibestudio-membank",
        context_spec=vt.ReasoningEngineContextSpec(
            memory_bank_config=vt.ReasoningEngineContextSpecMemoryBankConfig(
                customization_configs=[vt.MemoryBankCustomizationConfig(
                    memory_topics=[
                        topic(custom_memory_topic=custom(
                            label="CHANNEL_LESSONS",
                            description="What a published video's retention "
                                        "outcome taught the channel.")),
                        topic(custom_memory_topic=custom(
                            label="CHANNEL_CONSTRAINTS",
                            description="Standing rules every future script "
                                        "must obey (e.g. hook timing).")),
                        topic(custom_memory_topic=custom(
                            label="AUDIENCE",
                            description="Who this channel's finishers are and "
                                        "what else they finish.")),
                    ])])))


def engine_name(create: bool = False) -> str | None:
    if ENGINE_CACHE.exists():
        return json.loads(ENGINE_CACHE.read_text())["name"]
    if not create:
        return None
    if os.environ.get("STUDIO_DEMO") == "1":
        raise RuntimeError(
            "refusing to create an Agent Engine in a read-only deployment - "
            "runs/memorybank.json should have been baked into the image")
    eng = _cli().agent_engines.create(config=_bank_config())
    ENGINE_CACHE.write_text(json.dumps({"name": eng.api_resource.name}))
    return eng.api_resource.name


def _parse(fact: str) -> dict:
    topic = "NOTE"
    body = fact
    if fact.startswith("[") and "]" in fact:
        topic, body = fact[1:].split("]", 1)
    return {"topic": topic.strip(), "fact": body.strip()}


def recall(query: str = "what has this channel learned: lessons, rules, audience?"
           ) -> list[dict]:
    if os.environ.get("STUDIO_NO_MB"):
        return []
    name = engine_name()
    if not name:
        return []
    got = _cli().agent_engines.memories.retrieve(
        name=name, scope=SCOPE, similarity_search_params={"search_query": query})
    out = []
    for rm in got:
        m = getattr(rm, "memory", None)
        if m and getattr(m, "fact", None):
            ut = getattr(m, "update_time", None)
            out.append({"id": m.name.split("/")[-1],
                        "updated": str(ut)[:19] if ut else "",
                        **_parse(m.fact)})
    return out


def list_all() -> list[dict]:
    """Everything this channel remembers, in full.

    The Studio Memory tab is a LEDGER, not a search box - it has to show facts
    the agent would never retrieve for a given question, or the governance view
    lies by omission. `retrieve` is similarity search and belongs to the agent's
    read path; `list` belongs here.
    """
    if os.environ.get("STUDIO_NO_MB"):
        return []
    name = engine_name()
    if not name:
        return []
    out = []
    for m in _cli().agent_engines.memories.list(name=name):
        if not getattr(m, "fact", None):
            continue
        ut = getattr(m, "update_time", None)
        out.append({"id": m.name.split("/")[-1],
                    "updated": str(ut)[:19] if ut else "",
                    **_parse(m.fact)})
    return out


def write_facts(facts: list[str]) -> list[dict]:
    """memories.generate via the SDK (NOT the ADK wrapper) - for the action flags."""
    from vertexai._genai import types as vt
    name = engine_name()
    if not name:
        raise RuntimeError("no Memory Bank connected - provision it first: "
                           "python -m agent.bank")
    op = _cli().agent_engines.memories.generate(
        name=name,
        direct_memories_source=vt.GenerateMemoriesRequestDirectMemoriesSource(
            direct_memories=[{"fact": f} for f in facts]),
        scope=SCOPE, config={"wait_for_completion": True})
    flags = []
    resp = getattr(op, "response", None)
    for g in (getattr(resp, "generated_memories", None) or []):
        mem = getattr(g, "memory", None)
        flags.append({
            "action": str(getattr(g, "action", "")).split(".")[-1],
            "id": (getattr(mem, "name", "") or "").split("/")[-1]})
    return flags


def forget(memory_id: str) -> None:
    """The steering wheel: a wrong lesson gets corrected, not retrained."""
    _cli().agent_engines.memories.delete(
        name=f"{engine_name()}/memories/{memory_id}")


def inject(fact: str) -> list[dict]:
    """Hand-write a memory (the other half of the steering wheel)."""
    return write_facts([fact])
