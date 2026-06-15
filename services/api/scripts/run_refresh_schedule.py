from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parents[1]))

from app.db.session import SessionLocal
from app.scheduler.refresh import RefreshScheduler


def main() -> None:
    parser = argparse.ArgumentParser(description="Run a scheduled low-frequency data refresh plan.")
    parser.add_argument(
        "--cadence",
        choices=["auto", "daily_00", "daily_12", "post_match", "weekly"],
        default="auto",
        help="Refresh cadence to run. auto chooses by local Asia/Shanghai time and post-match context.",
    )
    parser.add_argument("--dry-run", action="store_true", help="Print the plan without executing tasks.")
    parser.add_argument("--force", action="store_true", help="Ignore once-per-slot completion checks.")
    parser.add_argument("--continue-on-error", action="store_true", help="Run remaining tasks after a task fails.")
    args = parser.parse_args()

    with SessionLocal() as db:
        result = RefreshScheduler(db).run(
            cadence=args.cadence,
            dry_run=args.dry_run,
            force=args.force,
            stop_on_error=not args.continue_on_error,
        )

    print(json.dumps(result, ensure_ascii=False, indent=2, default=str))
    if result["status"] == "failed":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
