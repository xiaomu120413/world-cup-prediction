import json
from collections.abc import Callable
from typing import TypeVar

from app.core.config import Settings

T = TypeVar("T")


def cached_json(settings: Settings, key: str, producer: Callable[[], T]) -> T:
    if not settings.cache_enabled:
        return producer()

    try:
        from redis import Redis
        from redis.exceptions import RedisError
    except ImportError:
        return producer()

    try:
        client = Redis.from_url(settings.redis_url, decode_responses=True)
        cached_value = client.get(key)
        if cached_value:
            return json.loads(cached_value)

        value = producer()
        client.setex(key, settings.cache_ttl_seconds, json.dumps(value, ensure_ascii=False))
        return value
    except (RedisError, TypeError, ValueError):
        return producer()
