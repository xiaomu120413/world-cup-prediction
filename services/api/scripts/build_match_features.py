from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parents[1]))

from app.db.session import SessionLocal
from app.features.match_features import MatchFeatureBuilder


def main() -> None:
    parser = argparse.ArgumentParser(description="Build model-ready match feature snapshots.")
    parser.add_argument("--match-id", action="append", dest="match_ids", help="Match public_id to build. Repeatable.")
    parser.add_argument(
        "--include-non-roster-matches",
        action="store_true",
        help="Also build features for matches whose teams do not both have Dongqiudi DQD-P roster coverage.",
    )
    parser.add_argument("--dry-run", action="store_true", help="Build feature payloads without writing model_features.")
    args = parser.parse_args()

    with SessionLocal() as db:
        result = MatchFeatureBuilder(db).build(
            public_ids=args.match_ids,
            dry_run=args.dry_run,
            roster_only=not args.include_non_roster_matches,
        )

    print(json.dumps(result, ensure_ascii=False, indent=2, default=str))


if __name__ == "__main__":
    main()
