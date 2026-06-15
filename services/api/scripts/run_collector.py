import argparse
from pathlib import Path
import sys

sys.path.append(str(Path(__file__).resolve().parents[1]))

from app.collectors.runner import CollectorRunner
from app.db.session import SessionLocal


def main() -> None:
    parser = argparse.ArgumentParser(description="Run a data collector.")
    parser.add_argument("--source", default="local_sample")
    parser.add_argument("--source-type", default="schedule")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    with SessionLocal() as db:
        result = CollectorRunner(db).run(args.source, args.source_type, dry_run=args.dry_run)
    print(result)


if __name__ == "__main__":
    main()
