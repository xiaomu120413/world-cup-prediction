from __future__ import annotations

import hashlib
import json
from datetime import datetime
from zoneinfo import ZoneInfo

from sqlalchemy import insert, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.orm import Session

from app.collectors.adapters import RawSnapshot, build_adapter
from app.collectors.normalizers import news_items_from_snapshot
from app.db.schema import collector_runs, news_items, raw_snapshots

API_TZ = ZoneInfo("Asia/Shanghai")


def snapshot_checksum(snapshot: RawSnapshot) -> str:
    raw = json.dumps(snapshot.payload, sort_keys=True, ensure_ascii=False, separators=(",", ":"))
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


class CollectorRunner:
    def __init__(self, db: Session):
        self.db = db

    def run(self, source: str, source_type: str, dry_run: bool = False) -> dict:
        started_at = datetime.now(API_TZ)
        try:
            snapshot = build_adapter(source, source_type).fetch()
            checksum = snapshot_checksum(snapshot)
            if dry_run:
                normalized_records = news_items_from_snapshot(snapshot)
                return {
                    "status": "completed",
                    "source": source,
                    "source_type": source_type,
                    "dry_run": True,
                    "records_read": self.count_records(snapshot),
                    "records_written": 0,
                    "normalized_records": len(normalized_records),
                    "checksum": checksum,
                }

            snapshot_id, inserted = self.write_snapshot(snapshot, checksum)
            normalized_written = self.write_normalized_records(snapshot)
            self.write_run(
                source=source,
                source_type=source_type,
                status="success",
                started_at=started_at,
                records_read=self.count_records(snapshot),
                records_written=(1 if inserted else 0) + normalized_written,
                snapshot_ids=[snapshot_id],
            )
            self.db.commit()
            return {
                "status": "completed",
                "source": source,
                "source_type": source_type,
                "dry_run": False,
                "records_read": self.count_records(snapshot),
                "records_written": (1 if inserted else 0) + normalized_written,
                "raw_snapshot_written": inserted,
                "normalized_records_written": normalized_written,
                "snapshot_ids": [str(snapshot_id)],
                "checksum": checksum,
            }
        except Exception as exc:
            if not dry_run:
                self.write_run(
                    source=source,
                    source_type=source_type,
                    status="failed",
                    started_at=started_at,
                    records_read=0,
                    records_written=0,
                    snapshot_ids=[],
                    error_message=str(exc),
                )
                self.db.commit()
            raise

    @staticmethod
    def count_records(snapshot: RawSnapshot) -> int:
        for value in snapshot.payload.values():
            if isinstance(value, list):
                return len(value)
        return 1

    def write_snapshot(self, snapshot: RawSnapshot, checksum: str):
        statement = (
            pg_insert(raw_snapshots)
            .values(
                source=snapshot.source,
                source_type=snapshot.source_type,
                source_url=snapshot.source_url,
                checksum=checksum,
                payload=snapshot.payload,
                parser_version=snapshot.parser_version,
            )
            .on_conflict_do_nothing(index_elements=["source", "source_type", "checksum"])
            .returning(raw_snapshots.c.id)
        )
        inserted_id = self.db.execute(statement).scalar_one_or_none()
        if inserted_id is not None:
            return inserted_id, True

        existing_id = self.db.execute(
            select(raw_snapshots.c.id).where(
                raw_snapshots.c.source == snapshot.source,
                raw_snapshots.c.source_type == snapshot.source_type,
                raw_snapshots.c.checksum == checksum,
            )
        ).scalar_one()
        return existing_id, False

    def write_normalized_records(self, snapshot: RawSnapshot) -> int:
        values = news_items_from_snapshot(snapshot)
        if not values:
            return 0

        statement = (
            pg_insert(news_items)
            .values(values)
            .on_conflict_do_nothing(index_elements=["source_url"])
            .returning(news_items.c.id)
        )
        return len(self.db.execute(statement).all())

    def write_run(
        self,
        source: str,
        source_type: str,
        status: str,
        started_at: datetime,
        records_read: int,
        records_written: int,
        snapshot_ids: list,
        error_message: str | None = None,
    ) -> None:
        self.db.execute(
            insert(collector_runs).values(
                source=source,
                job_type=source_type,
                status=status,
                started_at=started_at,
                finished_at=datetime.now(API_TZ),
                records_read=records_read,
                records_written=records_written,
                error_message=error_message,
                snapshot_ids=snapshot_ids,
            )
        )
