"""`python -m agent.run "hint"` - start a lap: research fans out, then the
graph pauses on YOU (first the topic chat, then the creative form)."""
import sys

from . import lap, state


def main():
    hint = sys.argv[1] if len(sys.argv) > 1 else ""
    kickoff = lap.start_lap(hint)
    print(f"── lap {state.load()['lap']} · {state.load()['run_id']} · research ──")
    lap.leg(kickoff)
    lap.print_where()


if __name__ == "__main__":
    main()
