import pytest

from app.llm import retry


@pytest.fixture(autouse=True)
def no_sleep(monkeypatch):
    sleeps: list[float] = []
    monkeypatch.setattr(retry.time, "sleep", sleeps.append)
    return sleeps


def flaky(errors: list[Exception], result="ok"):
    calls = {"n": 0}

    def fn():
        calls["n"] += 1
        if errors:
            raise errors.pop(0)
        return result

    return fn, calls


def test_retries_rate_limit_then_succeeds(no_sleep) -> None:
    fn, calls = flaky([RuntimeError("429 RESOURCE_EXHAUSTED")] * 2)
    assert retry.call_with_429_backoff(fn) == "ok"
    assert calls["n"] == 3 and no_sleep == [5.0, 10.0]  # exponential


def test_retries_brief_server_error_but_only_three_times() -> None:
    fn, calls = flaky([RuntimeError("503 UNAVAILABLE")] * 10)
    with pytest.raises(RuntimeError):
        retry.call_with_429_backoff(fn)
    assert calls["n"] == 3


def test_recovers_from_one_server_error() -> None:
    class ServerError(Exception):
        pass

    fn, calls = flaky([ServerError("model overloaded")])
    assert retry.call_with_429_backoff(fn) == "ok" and calls["n"] == 2


def test_other_errors_are_not_retried() -> None:
    fn, calls = flaky([ValueError("bad request 400")])
    with pytest.raises(ValueError):
        retry.call_with_429_backoff(fn)
    assert calls["n"] == 1
