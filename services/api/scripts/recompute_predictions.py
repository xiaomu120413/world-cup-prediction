import argparse
from pathlib import Path
import sys

sys.path.append(str(Path(__file__).resolve().parents[1]))

from app.db.session import SessionLocal
from app.predictions.service import DEFAULT_PREDICTION_MODEL_VERSION, BaselinePredictionService


def main() -> None:
    parser = argparse.ArgumentParser(description="Recompute match predictions.")
    parser.add_argument("--scope", default="matchday")
    parser.add_argument("--model-version", default=DEFAULT_PREDICTION_MODEL_VERSION)
    parser.add_argument("--model-kind", choices=("scoreline", "small_outcome", "baseline"), default=None)
    parser.add_argument("--seed", type=int)
    parser.add_argument("--match-id", action="append", dest="match_ids")
    args = parser.parse_args()

    with SessionLocal() as db:
        result = BaselinePredictionService(db).recompute(
            scope=args.scope,
            match_ids=args.match_ids,
            model_version=args.model_version,
            model_kind=args.model_kind,
            seed=args.seed,
        )
    print(result)


if __name__ == "__main__":
    main()
