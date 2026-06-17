import json
import time
from collections.abc import Callable
from threading import Lock
from typing import TypeVar

from app.core.config import Settings

T = TypeVar("T")

_memory_cache: dict[str, tuple[float, object]] = {}
_memory_cache_lock = Lock()
_redis_unavailable_until = 0.0
_redis_state_lock = Lock()
_REDIS_RETRY_DELAY_SECONDS = 30.0
_REDIS_TIMEOUT_SECONDS = 0.1


def _get_memory_value(key: str) -> object | None:
    now = time.monotonic()
    with _memory_cache_lock:
        cached = _memory_cache.get(key)
        if not cached:
            return None
        expires_at, value = cached
        if expires_at <= now:
            _memory_cache.pop(key, None)
            return None
        return value


def _set_memory_value(key: str, value: object, ttl_seconds: int) -> None:
    with _memory_cache_lock:
        _memory_cache[key] = (time.monotonic() + ttl_seconds, value)


def _redis_is_available() -> bool:
    with _redis_state_lock:
        return time.monotonic() >= _redis_unavailable_until


def _mark_redis_unavailable() -> None:
    global _redis_unavailable_until
    with _redis_state_lock:
        _redis_unavailable_until = time.monotonic() + _REDIS_RETRY_DELAY_SECONDS


def cached_json(settings: Settings, key: str, producer: Callable[[], T]) -> T:
    if not settings.cache_enabled:
        return producer()

    memory_value = _get_memory_value(key)
    if memory_value is not None:
        return memory_value  # type: ignore[return-value]

    redis_client = None
    redis_error: type[Exception] = Exception
    if settings.redis_url and _redis_is_available():
        try:
            from redis import Redis
            from redis.exceptions import RedisError

            redis_error = RedisError
            redis_client = Redis.from_url(
                settings.redis_url,
                decode_responses=True,
                socket_connect_timeout=_REDIS_TIMEOUT_SECONDS,
                socket_timeout=_REDIS_TIMEOUT_SECONDS,
                retry_on_timeout=False,
            )
        except ImportError:
            redis_client = None

    if redis_client is not None:
        try:
            cached_value = redis_client.get(key)
            if cached_value:
                value = json.loads(cached_value)
                try:
                    _set_memory_value(key, value, settings.cache_ttl_seconds)
                except TypeError:
                    pass
                return value
        except (redis_error, TypeError, ValueError):
            _mark_redis_unavailable()
            redis_client = None

    value = producer()

    if redis_client is not None:
        try:
            redis_client.setex(key, settings.cache_ttl_seconds, json.dumps(value, ensure_ascii=False))
            return value
        except (redis_error, TypeError, ValueError):
            _mark_redis_unavailable()
            pass

    try:
        _set_memory_value(key, value, settings.cache_ttl_seconds)
    except TypeError:
        return value

    return value
