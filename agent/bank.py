"""`python -m agent.bank` - provision the channel's Memory Bank (one-time).

Memory Bank lives ON an Agent Engine resource in YOUR project. This command
creates that resource (or attaches to the one already cached), prints its
full resource name, and shows the scope every note will be filed under.
The name is cached in runs/memorybank.json - that file IS the connection.
"""
from . import config, memory


def main():
    cached = memory.engine_name()
    if cached:
        print(f"already connected (runs/memorybank.json):\n  {cached}")
    else:
        print("no Memory Bank yet - creating an Agent Engine to host it "
              "(~30s, one-time)…")
        name = memory.engine_name(create=True)
        print(f"── created ──\n  {name}")
    print(f"scope for every note: app_name={config.APP} · user_id={config.USER}")
    topics = [t.custom_memory_topic.label
              for c in (memory._bank_config().context_spec
                        .memory_bank_config.customization_configs)
              for t in c.memory_topics]
    print(f"memory topics (custom): {' · '.join(topics)}")
    notes = memory.list_all()
    print(f"the bank holds {len(notes)} note(s)")
    for m in notes:
        print(f"  memory#{m['id'][:8]} [{m['topic']}] {m['fact'][:70]}")


if __name__ == "__main__":
    main()
