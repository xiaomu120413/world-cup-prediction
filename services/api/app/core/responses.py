from datetime import datetime
from typing import Any
from uuid import uuid4
from zoneinfo import ZoneInfo

from fastapi import HTTPException

API_TZ = ZoneInfo("Asia/Shanghai")


def now_iso() -> str:
    return datetime.now(API_TZ).isoformat(timespec="seconds")


def request_id() -> str:
    return f"req_{uuid4().hex[:12]}"


def envelope(data: Any, **meta: Any) -> dict[str, Any]:
    return {
        "data": data,
        "meta": {
            "updated_at": meta.pop("updated_at", now_iso()),
            "version": meta.pop("version", "v1"),
            "request_id": meta.pop("request_id", request_id()),
            **meta,
        },
    }


def list_envelope(data: list[Any], **meta: Any) -> dict[str, Any]:
    return envelope(data, count=len(data), **meta)


def not_found(code: str, message: str) -> HTTPException:
    return HTTPException(status_code=404, detail={"code": code, "message": message, "details": {}})

