"""Analytics backend selection tests."""

from __future__ import annotations

import pytest

from aurora_analytics import get_analytics_backend


def test_default_backend_is_postgres(monkeypatch):
    monkeypatch.delenv("ANALYTICS_BACKEND", raising=False)
    assert get_analytics_backend() == "postgres"


def test_clickhouse_backend(monkeypatch):
    monkeypatch.setenv("ANALYTICS_BACKEND", "clickhouse")
    assert get_analytics_backend() == "clickhouse"


def test_invalid_backend_raises(monkeypatch):
    monkeypatch.setenv("ANALYTICS_BACKEND", "snowflake")
    with pytest.raises(ValueError, match="Invalid ANALYTICS_BACKEND"):
        get_analytics_backend()
