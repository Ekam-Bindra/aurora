"""SQLite DATABASE_URL normalization for monorepo-relative paths."""

from aurora.persistence import _normalize_database_url


def test_normalize_relative_sqlite_path(tmp_path, monkeypatch):
    from aurora import persistence

    monkeypatch.setattr(persistence, "_REPO_ROOT", tmp_path)
    url = _normalize_database_url("sqlite:///./data/test.db")
    assert url == f"sqlite:///{tmp_path / 'data' / 'test.db'}"
    assert (tmp_path / "data" / "test.db").parent.exists()
