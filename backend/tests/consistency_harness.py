"""Score the same transcript five times and measure the spread.

    cd backend && .venv/bin/python -m tests.consistency_harness

This is the load-bearing property of the whole product. CLAUDE.md:

    the same transcript scored twice will drift 15-20 points if you ask
    for a single number. Sub-scores anchored to named rubric criteria hold
    steady. The client will re-run the same candidate during a demo.

There is no ground truth for a screening score, so correctness is not
measurable. Variance is. If the range across identical runs is wide, the
scores are noise regardless of how reasonable any single one looks, and
re-running a candidate in front of a client will produce a different
number and destroy trust in the whole thing.

Not part of the pytest suite: it makes real API calls. Run it after any
change to the screening prompt or the rubric prompt.
"""

from __future__ import annotations

import logging
import statistics
import sys

from app.core.config import get_settings
from app.core.heuristics import (
    CONSISTENCY_HARNESS_MAX_SCORE_RANGE,
    CONSISTENCY_HARNESS_RUNS,
)
from app.services.screening import screen_candidate
from tests.fixtures.candidates import GOLDEN_RESUME, GOLDEN_TRANSCRIPT
from tests.fixtures.rubrics import valid_rubric

logging.basicConfig(level=logging.WARNING, format="%(levelname)s %(name)s: %(message)s")

SKILLS = ["Python", "Django", "PostgreSQL", "REST APIs", "System design"]


def main() -> int:
    settings = get_settings()
    if settings.demo_mode:
        sys.exit(
            "DEMO_MODE is on, so every run would replay one recorded answer "
            "and the spread would be a meaningless zero. Turn it off."
        )
    if not settings.gemini_keys():
        sys.exit("Set GEMINI_API_KEY in backend/.env.")

    rubric = valid_rubric()
    totals: list[int] = []
    per_criterion: dict[str, list[int]] = {c.id: [] for c in rubric.criteria}

    print(f"Scoring the same transcript {CONSISTENCY_HARNESS_RUNS} times.\n")

    for run in range(1, CONSISTENCY_HARNESS_RUNS + 1):
        result = screen_candidate(rubric, GOLDEN_TRANSCRIPT, GOLDEN_RESUME, SKILLS)
        totals.append(result.total_score)
        for sub in result.sub_scores:
            per_criterion.setdefault(sub.criterion_id, []).append(sub.points_awarded)
        print(f"  run {run}: {result.total_score:3d}  ({result.recommendation})")

    spread = max(totals) - min(totals)
    print(
        f"\nTotal: min {min(totals)}  max {max(totals)}  "
        f"mean {statistics.mean(totals):.1f}  range {spread}"
    )

    # Per-criterion spread is the diagnostic. A wide total is always caused
    # by one or two criteria disagreeing with themselves, and naming them
    # is what makes the prompt fixable rather than just failing.
    print("\nPer criterion:")
    worst = []
    for criterion in rubric.criteria:
        values = per_criterion.get(criterion.id) or []
        if not values:
            continue
        criterion_spread = max(values) - min(values)
        worst.append((criterion_spread, criterion.name, values))
        print(
            f"  {criterion.name:<34} {values}  range {criterion_spread}"
            f"  / {criterion.points}"
        )

    worst.sort(reverse=True)
    if worst and worst[0][0] > 0:
        print(f"\nWidest: {worst[0][1]} (range {worst[0][0]}).")

    if spread > CONSISTENCY_HARNESS_MAX_SCORE_RANGE:
        print(
            f"\nFAIL: range {spread} exceeds the "
            f"{CONSISTENCY_HARNESS_MAX_SCORE_RANGE} point threshold in "
            f"app/core/heuristics.py.\n"
            "The scores are drifting. Tighten the criterion descriptions the "
            "harness named above before shipping this prompt."
        )
        return 1

    print(
        f"\nPASS: range {spread} is within the "
        f"{CONSISTENCY_HARNESS_MAX_SCORE_RANGE} point threshold."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
