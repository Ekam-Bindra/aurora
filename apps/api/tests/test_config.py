"""Settings parsing that only container environments exercise."""

from __future__ import annotations

from aurora.core.config import Settings


def test_cors_origins_accepts_comma_string(monkeypatch):
    monkeypatch.setenv("CORS_ORIGINS", "https://a.example, https://b.example")
    assert Settings().cors_origins == ["https://a.example", "https://b.example"]


def test_cors_origins_accepts_json_array(monkeypatch):
    monkeypatch.setenv("CORS_ORIGINS", '["https://a.example", "https://b.example"]')
    assert Settings().cors_origins == ["https://a.example", "https://b.example"]


def test_cors_origins_default_without_env(monkeypatch):
    monkeypatch.delenv("CORS_ORIGINS", raising=False)
    assert "http://localhost:3000" in Settings().cors_origins
