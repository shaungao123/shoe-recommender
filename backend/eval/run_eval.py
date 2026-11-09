"""Compares recommendation rankers on labeled shopper profiles.

Run from backend/: ``python -m eval.run_eval [--only SUBSTRING] [--verbose]``.
Needs DATABASE_URL and OPENAI_API_KEY. Reads the database in a READ ONLY
transaction and makes one embedding call per case; the LLM explainer isn't used.

Label score is the headline: it is independent of the ranker's inputs. Answer
fit reuses the ratings the boosts read, so it shows answers are honored, not
that picks are good.
"""

from __future__ import annotations

import argparse
import json
import re
from dataclasses import dataclass
from pathlib import Path
from statistics import mean

from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session

from app.schemas.candidate import Candidate
from app.schemas.recommend import RecommendRequest
from app.services.rag.retriever import retrieve, retrieve_fallback
from app.services.ranking import _outdoor_value, _priority_value, select_top_candidates
from app.services.recommend import FALLBACK_POOL, RANKING_POOL, TOP_N, _shopper_profile
from eval.cases import CASES, Case
from shared.config import settings

LAST_RUN = Path(__file__).parent / "last_run.json"
GOOD_RATING_VALUE = 0.6  # 8.0+ on a 10-point rating, or about 13.6 oz or lighter
OUTDOOR_READY = 0.6
REGRESSION_MARGIN = 0.01


@dataclass(frozen=True)
class Pools:
    keyword: list[Candidate]
    vector: list[Candidate]


def label(pick: Candidate, case: Case) -> int:
    """+1 for a labeled good fit, -1 for a labeled bad fit, 0 when unlabeled."""
    name = f"{pick.brand} {pick.name}"
    matches = lambda patterns: any(re.search(p, name, re.IGNORECASE) for p in patterns)
    if matches(case.bad):
        return -1
    return 1 if matches(case.good) else 0


def answer_fit(pick: Candidate, request: RecommendRequest) -> float | None:
    """Share of the shopper's stated preferences this shoe meets; None if none apply."""
    checks: list[bool] = []
    specs = pick.specs or {}
    checks += [_priority_value(pick, p)[0] >= GOOD_RATING_VALUE for p in request.priorities]
    if request.court == "outdoor":
        checks.append(_outdoor_value(pick)[0] >= OUTDOOR_READY)
    if request.preferred_brand:
        checks.append(pick.brand.lower() == request.preferred_brand.lower())
    if request.preferred_cut:
        checks.append(specs.get("cut_height") == request.preferred_cut)
    if request.foot_width and request.foot_width != "standard":
        checks.append(specs.get("width_fit") == request.foot_width)
    return mean(checks) if checks else None


def grade(picks: list[Candidate], case: Case, request: RecommendRequest) -> dict:
    labels = [label(pick, case) for pick in picks]
    fits = [fit for pick in picks if (fit := answer_fit(pick, request)) is not None]
    brand = (request.preferred_brand or "").lower()
    return {
        "picks": [f"{p.brand} {p.name}" for p in picks],
        "labels": labels,
        "label_score": mean(labels) if labels else 0.0,
        "answer_fit": mean(fits) if fits else None,
        "over_budget": sum(
            1 for p in picks if request.budget is not None and (p.price or 0) > request.budget
        ),
        "all_preferred_brand": bool(brand) and all(p.brand.lower() == brand for p in picks),
    }


def rank_all(pools: Pools, case: Case, request: RecommendRequest) -> dict[str, dict]:
    return {
        "keyword": grade(select_top_candidates(pools.keyword, TOP_N), case, request),
        "similarity": grade(select_top_candidates(pools.vector, TOP_N), case, request),
        "boosted": grade(select_top_candidates(pools.vector, TOP_N, request=request), case, request),
    }


def summarize(results: dict[str, dict[str, dict]]) -> dict[str, dict[str, float]]:
    summary: dict[str, dict[str, float]] = {}
    for ranker in ("keyword", "similarity", "boosted"):
        rows = [ranks[ranker] for ranks in results.values()]
        labels = [value for row in rows for value in row["labels"]]
        fits = [row["answer_fit"] for row in rows if row["answer_fit"] is not None]
        summary[ranker] = {
            "label_score": mean(row["label_score"] for row in rows),
            "good_rate": labels.count(1) / len(labels),
            "bad_rate": labels.count(-1) / len(labels),
            "answer_fit": mean(fits) if fits else 0.0,
            "over_budget": sum(row["over_budget"] for row in rows),
            "all_preferred_brand": sum(row["all_preferred_brand"] for row in rows),
        }
    return summary


def regressions(results: dict[str, dict[str, dict]], previous: dict[str, float]) -> list[str]:
    return [
        f"{case_id}: {previous[case_id]:+.2f} -> {ranks['boosted']['label_score']:+.2f}"
        for case_id, ranks in results.items()
        if case_id in previous
        and ranks["boosted"]["label_score"] < previous[case_id] - REGRESSION_MARGIN
    ]


def load_pools(session: Session, cases: list[Case]) -> dict[str, Pools]:
    pools: dict[str, Pools] = {}
    for case in cases:
        request = RecommendRequest(**case.request)
        profile = _shopper_profile(request)
        pools[case.id] = Pools(
            keyword=retrieve_fallback(
                session, playstyle=profile, budget=request.budget, limit=FALLBACK_POOL
            ),
            vector=retrieve(
                session, playstyle=profile, budget=request.budget, aesthetic="", limit=RANKING_POOL
            ),
        )
    return pools


def evaluate(pools: dict[str, Pools], cases: list[Case]) -> dict[str, dict[str, dict]]:
    return {
        case.id: rank_all(pools[case.id], case, RecommendRequest(**case.request)) for case in cases
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--only", default="", help="Only run cases whose id contains this text")
    parser.add_argument("--verbose", action="store_true", help="Print each case's picks")
    parser.add_argument("--save", action="store_true", help="Record scores for regression checks")
    args = parser.parse_args()

    cases = [case for case in CASES if args.only in case.id]
    engine = create_engine(settings.database_url)
    with Session(engine) as session:
        session.execute(text("SET TRANSACTION READ ONLY"))
        pools = load_pools(session, cases)
        session.rollback()

    results = evaluate(pools, cases)
    if args.verbose:
        for case_id, ranks in results.items():
            print(f"\n{case_id}")
            for ranker, row in ranks.items():
                print(f"  {ranker:<10} {row['label_score']:+.2f}  {list(zip(row['picks'], row['labels']))}")

    print(f"\n{'ranker':<11}{'label':>7}{'good':>7}{'bad':>7}{'fit':>7}{'over$':>7}{'brand-only':>12}")
    for ranker, row in summarize(results).items():
        print(
            f"{ranker:<11}{row['label_score']:>+7.2f}{row['good_rate']:>7.0%}{row['bad_rate']:>7.0%}"
            f"{row['answer_fit']:>7.0%}{row['over_budget']:>7}{row['all_preferred_brand']:>12}"
        )

    if LAST_RUN.exists():
        dropped = regressions(results, json.loads(LAST_RUN.read_text()))
        print("\nRegressions since last saved run:", dropped or "none")
    if args.save:
        scores = {case_id: ranks["boosted"]["label_score"] for case_id, ranks in results.items()}
        LAST_RUN.write_text(json.dumps(scores, indent=2) + "\n")


if __name__ == "__main__":
    main()
