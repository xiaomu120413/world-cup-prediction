import argparse
from pathlib import Path
import sys

sys.path.append(str(Path(__file__).resolve().parents[1]))

from app.collectors.runner import CollectorRunner
from app.db.session import SessionLocal

REAL_COLLECTOR_SOURCES = {"dongqiudi", "thestatsapi"}


def main() -> None:
    parser = argparse.ArgumentParser(description="Run a data collector.")
    parser.add_argument("--source", required=True, help="Collector source, for example dongqiudi or thestatsapi.")
    parser.add_argument("--source-type", default="schedule")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    if args.source not in REAL_COLLECTOR_SOURCES:
        parser.error(f"--source must be one of: {', '.join(sorted(REAL_COLLECTOR_SOURCES))}")

    with SessionLocal() as db:
        result = CollectorRunner(db).run(args.source, args.source_type, dry_run=args.dry_run)
    print(result)


if __name__ == "__main__":
    main()
