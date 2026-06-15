from collections.abc import Callable
from typing import TypeVar

from app.core.config import Settings
from app.db.session import SessionLocal
from app.repositories.public_data import PublicDataRepository

T = TypeVar("T")


def use_database(settings: Settings) -> bool:
    return settings.data_backend.lower() == "database"


def with_public_repository(callback: Callable[[PublicDataRepository], T]) -> T:
    with SessionLocal() as db:
        return callback(PublicDataRepository(db))
