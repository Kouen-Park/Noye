"""A first launch must finish database setup before accepting requests."""

from concurrent.futures import ThreadPoolExecutor

from fastapi.testclient import TestClient

from app.config import get_settings
from app.db.database import connect
from app.main import app


def test_fresh_database_is_ready_before_parallel_library_requests(tmp_path, monkeypatch):
    path = tmp_path / "fresh.db"
    monkeypatch.setattr(get_settings(), "database_url", f"sqlite:///{path}")

    with TestClient(app) as client:
        # Assert this before any request: an implementation that initializes
        # lazily inside get_db would still leave first requests racing.
        assert path.exists()
        connection = connect(path)
        try:
            assert connection.execute("PRAGMA journal_mode").fetchone()[0] == "wal"
            assert connection.execute("SELECT COUNT(*) FROM files").fetchone()[0] == 0
        finally:
            connection.close()

        with ThreadPoolExecutor(max_workers=2) as pool:
            responses = list(pool.map(client.get, ["/files", "/index/status"]))
        assert [response.status_code for response in responses] == [200, 200]
        assert responses[0].json() == []
        assert responses[1].json()["ready_files"] == 0
