from app.core.cache import cached_json
from app.core.config import Settings


def test_cached_json_disabled_returns_producer_value():
    settings = Settings(cache_enabled=False)

    assert cached_json(settings, "test:key", lambda: {"value": 1}) == {"value": 1}


def test_cached_json_falls_back_when_redis_unavailable():
    settings = Settings(cache_enabled=True, redis_url="redis://127.0.0.1:1/0")

    assert cached_json(settings, "test:key", lambda: {"value": 2}) == {"value": 2}


def test_cached_json_uses_memory_cache_when_redis_unavailable():
    settings = Settings(cache_enabled=True, redis_url="redis://127.0.0.1:1/0", cache_ttl_seconds=60)
    calls = {"count": 0}

    def producer():
        calls["count"] += 1
        return {"value": calls["count"]}

    assert cached_json(settings, "test:memory-fallback", producer) == {"value": 1}
    assert cached_json(settings, "test:memory-fallback", producer) == {"value": 1}
    assert calls["count"] == 1
