from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime
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
    parser.add_argument(
        "--as-of-at",
        help="Snapshot timestamp, ISO-8601. Omit to write/update the current Asia/Shanghai daily pre-match snapshot.",
    )
    args = parser.parse_args()
    snapshot_as_of_at = datetime.fromisoformat(args.as_of_at) if args.as_of_at else None

    with SessionLocal() as db:
        result = MatchFeatureBuilder(db).build(
            public_ids=args.match_ids,
            dry_run=args.dry_run,
            roster_only=not args.include_non_roster_matches,
            snapshot_as_of_at=snapshot_as_of_at,
        )

    print(json.dumps(result, ensure_ascii=False, indent=2, default=str))


if __name__ == "__main__":
    main()
