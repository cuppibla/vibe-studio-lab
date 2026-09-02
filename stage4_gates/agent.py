"""Stage 4 - the gates, on a test bench. The decision core of the publish
workflow (agent/post.py), real nodes, both labeled edge dicts drawn.

The channel has exactly TWO routers and both are here: policy_check
(OK/BLOCK, reading agent/policy_words.txt at decision time) and eval_gate
(PASS/FAIL, deterministic conduct checks). The lap graph has zero routers -
it ships nothing, so it needs no gate; both gates stand in front of the one
side effect.

Two pieces of test equipment frame them, and neither is a fake:
  try_title        feeds the gate a title YOU type - gates are tested with
                   crafted inputs before they guard real traffic; in the
                   publish chapter the same gates check scripter's titles.
  hold_for_publish stands where publisher will. It cannot run here because
                   no renders exist yet - the decision core is pure and
                   testable without the world; the side-effect nodes
                   (editor, publisher) wait for the publish chapter.
"""
from google.adk import Event, Workflow
from google.adk.workflow import START

from agent import state
from agent.post import eval_gate, policy_check, quarantine, rejected


def try_title(node_input: str):
    """Test harness: your typed line becomes the script under test."""
    st = state.load()
    st["script"] = {"title": node_input, "description": "(gate test)",
                    "tags": ["test", "gate"]}
    st["lineage"] = {"evidence": [], "gates": {}}   # fresh verdicts every run
    state.save(st)
    return Event(output={"title_under_test": node_input})


def hold_for_publish(node_input):
    """Test harness: publisher's seat - reports clearance, causes nothing."""
    return Event(output={"cleared_for_publish": True,
                         "note": "publisher runs after real renders"})


root_agent = Workflow(
    name="stage4_gates",
    description="try_title -> policy_check -> eval_gate -> hold | quarantine | rejected",
    edges=[(START, try_title, policy_check),
           (policy_check, {"OK": eval_gate, "BLOCK": quarantine}),
           (eval_gate, {"PASS": hold_for_publish, "FAIL": rejected})])
