"""The adk web entry: `adk web .` finds this because the folder name is the
app name and this file exports root_agent. The desk agent is the root so the
chat box can drive section 1's mechanism live."""
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))
from agent.desk import render_desk  # noqa: E402

root_agent = render_desk
