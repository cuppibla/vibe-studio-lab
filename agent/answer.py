"""`python -m agent.answer --subject … --character … --style …` - submit the
creative form: ONE function_response, and the graph moves again."""
import argparse

from . import drive, lap


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--subject", required=True)
    ap.add_argument("--character", required=True)
    ap.add_argument("--style", required=True, choices=["low-poly", "paper", "bright"])
    a = ap.parse_args()
    w = lap.where()
    if w["phase"] != "form":
        print(f"nothing to answer — phase is {w['phase']}"); return
    cid, name = w["call"]
    lap.leg((cid, name, {"result": {"subject": a.subject, "character": a.character,
                                    "style": a.style}}))
    lap.print_where()


if __name__ == "__main__":
    main()
