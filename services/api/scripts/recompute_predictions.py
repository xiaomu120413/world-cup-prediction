import argparse
from pathlib import Path
import sys

sys.path.append(str(Path(__file__).resolve().parents[1]))

from app.db.session import SessionLocal
from app.predictions.service import BaselinePredictionService


def main() -> None:
    parser = argparse.ArgumentParser(description="Recompute baseline predictions.")
    parser.add_argument("--scope", default="matchday")
    parser.add_argument("--model-version", default="baseline_2026_06_13")
    parser.add_argument("--seed", type=int)
    parser.add_argument("--match-id", action="append", dest="match_ids")
    args = parser.parse_args()

    with SessionLocal() as db:
        result = BaselinePredictionService(db).recompute(
            scope=args.scope,
            match_ids=args.match_ids,
            model_version=args.model_version,
            seed=args.seed,
        )
    print(result)


if __name__ == "__main__":
    main()
