import argparse
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from app.db.init_db import init_database


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Initialize the World Cup Prediction database.")
    return parser.parse_args()


if __name__ == "__main__":
    parse_args()
    init_database()
