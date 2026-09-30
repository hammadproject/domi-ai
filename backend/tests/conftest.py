"""Shared test setup: no test may touch the real Redis (rate-limit counters, quota, cache)."""

import pytest

from app.api.deps import get_cache, get_quota_guard
from app.cache import Cache
from app.main import app
from app.quota import QuotaGuard
from app.ratelimit import RateLimiter, get_rate_limiter


class _State:
    def __init__(self) -> None:
        self.data: dict[str, str] = {}
        self.ttl: dict[str, int] = {}


class FakeSyncRedis:
    def __init__(self, state: _State | None = None) -> None:
        self.state = state or _State()

    def get(self, key):
        return self.state.data.get(key)

    def incr(self, key):
        n = int(self.state.data.get(key, 0)) + 1
        self.state.data[key] = str(n)
        return n

    def expire(self, key, seconds):
        self.state.ttl[key] = seconds
        return True


class _FakePipeline:
    def __init__(self, redis) -> None:
        self._redis, self._ops = redis, []

    async def __aenter__(self):
        return self

    async def __aexit__(self, *exc):
        return False

    def incr(self, key):
        self._ops.append(("incr", (key,)))

    def get(self, key):
        self._ops.append(("get", (key,)))

    def expire(self, key, seconds):
        self._ops.append(("expire", (key, seconds)))

    async def execute(self):
        return [await getattr(self._redis, name)(*args) for name, args in self._ops]


class FakeAsyncRedis:
    def __init__(self, state: _State | None = None) -> None:
        self.state = state or _State()

    async def get(self, key):
        return self.state.data.get(key)

    async def set(self, key, value, ex=None):
        self.state.data[key] = value
        if ex:
            self.state.ttl[key] = ex

    async def incr(self, key):
        n = int(self.state.data.get(key, 0)) + 1
        self.state.data[key] = str(n)
        return n

    async def expire(self, key, seconds):
        self.state.ttl[key] = seconds
        return True

    async def delete(self, *keys):
        for k in keys:
            self.state.data.pop(k, None)

    def pipeline(self, transaction=False):
        return _FakePipeline(self)

    async def scan_iter(self, match=None, count=None):
        prefix = (match or "").rstrip("*")
        for k in list(self.state.data):
            if k.startswith(prefix):
                yield k


@pytest.fixture(autouse=True)
def fake_infrastructure():
    state = _State()
    app.dependency_overrides[get_rate_limiter] = lambda: RateLimiter(FakeAsyncRedis(state))
    app.dependency_overrides[get_cache] = lambda: Cache(FakeAsyncRedis(state))
    app.dependency_overrides[get_quota_guard] = lambda: QuotaGuard(FakeSyncRedis(state), 1000)
    yield state
    app.dependency_overrides.clear()
