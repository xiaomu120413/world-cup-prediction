from __future__ import annotations

import json
from pathlib import Path
import sys

sys.path.append(str(Path(__file__).resolve().parents[1]))

from app.db.session import SessionLocal
from app.repositories.public_data import PublicDataRepository


def main() -> None:
    with SessionLocal() as db:
        audit = PublicDataRepository(db).get_real_data_audit()

    print(json.dumps(audit, ensure_ascii=False, indent=2))
    if audit["status"] != "pass":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
