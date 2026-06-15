import argparse
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from app.db.init_db import init_database


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Initialize the World Cup Prediction database.")
    parser.add_argument("--no-seed", action="store_true", help="Only create schema, do not insert mock seed data.")
    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()
    init_database(seed=not args.no_seed)
