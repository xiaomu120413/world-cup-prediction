from __future__ import annotations

import argparse
import csv
import sys
from pathlib import Path

from sqlalchemy import select

sys.path.append(str(Path(__file__).resolve().parents[1]))

from app.db.schema import players, teams
from app.db.session import SessionLocal


def main() -> None:
    parser = argparse.ArgumentParser(description="Export Dongqiudi roster players missing market values.")
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("data/exports/missing_player_market_values.csv"),
    )
    args = parser.parse_args()
    args.output.parent.mkdir(parents=True, exist_ok=True)

    with SessionLocal() as db:
        rows = db.execute(
            select(
                players.c.code.label("player_code"),
                teams.c.code.label("team_code"),
                players.c.name_en.label("player_name"),
            )
            .select_from(players.join(teams, teams.c.id == players.c.team_id))
            .where(players.c.code.like("DQD-P%"), players.c.market_value_eur.is_(None))
            .order_by(teams.c.code.asc(), players.c.shirt_number.asc())
        ).mappings().all()

    with args.output.open("w", encoding="utf-8", newline="") as file:
        fieldnames = [
            "player_code",
            "team_code",
            "player_name",
            "market_value_eur",
            "source_name",
            "source_url",
            "source_record_id",
            "confidence",
            "as_of_date",
        ]
        writer = csv.DictWriter(file, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow(
                {
                    "player_code": row.player_code,
                    "team_code": row.team_code,
                    "player_name": row.player_name,
                    "market_value_eur": "",
                    "source_name": "",
                    "source_url": "",
                    "source_record_id": "",
                    "confidence": "0.90",
                    "as_of_date": "",
                }
            )
    print(f"exported {len(rows)} rows to {args.output}")


if __name__ == "__main__":
    main()
