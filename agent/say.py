"""`python -m agent.say "text"` - talk to the topic gate (push back / accept)."""
import sys

from . import lap


def main():
    if len(sys.argv) < 2:
        print('usage: python -m agent.say "your reply"'); return
    lap.leg(sys.argv[1])
    lap.print_where()


if __name__ == "__main__":
    main()
