"""Library controls and health honor folder ownership and search eligibility."""

import pytest

from app.api import files as file_api
from app.api import index as index_api
from app.api import jobs as job_api
from app.db import files
from app.services.folders import update_root
from app.services.integrity import searchable_file_ids
from app.tests.test_folder_foundation import discover, folder


@pytest.mark.parametrize(
    "state", ["active", "paused", "disconnected", "unavailable", "missing", "stale"]
)
def test_health_matches_folder_search_eligibility_without_hiding_diagnosis(folder, state):
    db, _, root_id, _, _ = folder
    record = discover(folder)
    if state == "paused":
        update_root(db, root_id, processing=False)
    elif state == "disconnected":
        update_root(db, root_id, disconnect=True)
    elif state == "unavailable":
        db.execute("UPDATE source_roots SET availability='unavailable' WHERE id=?", (root_id,))
    elif state == "missing":
        db.execute("UPDATE sources SET availability='missing' WHERE file_id=?", (record.id,))
    elif state == "stale":
        db.execute("UPDATE sources SET version=? WHERE file_id=?", ("b" * 64, record.id))
    db.commit()
    health = index_api.index_status(False, db)
    assert (
        health.searchable_files == len(searchable_file_ids(db)) == (1 if state == "active" else 0)
    )
    assert health.ready_files == 1 and health.problems == []
    files.set_embedding_model(db, record.id, "old-model")
    diagnosed = index_api.index_status(False, db)
    assert diagnosed.searchable_files == 0
    assert diagnosed.problems[0].problems == ["MODEL_CHANGED"]
    assert not diagnosed.problems[0].searchable
    assert diagnosed.problems[0].folder_root_id == root_id


def test_folder_metadata_survives_pause_disconnect_and_polling(folder):
    db, _, root_id, _, _ = folder
    record = discover(folder)
    for controls in ({}, {"processing": False}, {"disconnect": True}):
        update_root(db, root_id, **controls)
        assert file_api.get_file(record.id, db).folder_root_id == root_id
        assert file_api.list_files(db)[0].folder_root_id == root_id
        assert job_api.list_jobs(db)[0]["folder_root_id"] == root_id
