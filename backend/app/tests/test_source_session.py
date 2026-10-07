"""Current version capture and short mutation exclusion, using real folder originals."""

import threading

import pytest

from app.services import ingestion
from app.services.folders import SourceError
from app.services.source_catalog import SourceSession
from app.tests.test_folder_foundation import discover, folder


def test_session_rejects_unobserved_external_edit_and_never_mixes_versions(folder):
    db, root, _, _, _ = folder
    record = discover(folder)
    session = SourceSession(db)
    assert "37" in session.read(record.id)[0]["content"]
    (root / "note.txt").write_text("The limit changed to 92.")
    with pytest.raises(SourceError, match="bytes no longer match"):
        session.verify()
    assert session.versions[record.id] == record.content_hash


def test_commit_guard_excludes_ingestion_delete_rebuild_and_releases_on_error(folder):
    db, _, _, _, _ = folder
    record = discover(folder)
    session = SourceSession(db)
    session.read(record.id)
    failures = []

    def mutate():
        for action in (ingestion.reserve_ingestion, ingestion.reserve_delete):
            try:
                action(record.id)
            except ingestion.AlreadyIngesting:
                failures.append("blocked")
        try:
            ingestion.begin_rebuild()
        except ingestion.MaintenanceBusy:
            failures.append("rebuild blocked")

    with pytest.raises(RuntimeError, match="artifact transaction failed"):
        with session.commit_guard():
            thread = threading.Thread(target=mutate)
            thread.start()
            thread.join(timeout=1)
            assert not thread.is_alive()
            raise RuntimeError("artifact transaction failed")
    assert failures == ["blocked", "blocked", "rebuild blocked"]
    ingestion.reserve_delete(record.id)
    ingestion.release_file(record.id)


def test_scope_and_active_ingestion_are_not_read_grants(folder):
    db, _, _, _, _ = folder
    record = discover(folder)
    with pytest.raises(SourceError, match="outside"):
        SourceSession(db, {"mode": "empty"}).read(record.id)
    session = SourceSession(db, {"mode": "chosen", "source_ids": [record.id]})
    ingestion.reserve_ingestion(record.id)
    try:
        with pytest.raises(SourceError) as failure:
            session.read(record.id)
        assert failure.value.code == "busy"
    finally:
        ingestion.release_file(record.id)
    assert session.read(record.id)
