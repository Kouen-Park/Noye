from app.services.folders import emit
from app.services.wiki import observer
from app.tests.test_folder_foundation import discover, folder, ingest
from app.tests.test_wiki_integration import workspace


def ready_event(db, identifier):
    source = dict(db.execute("SELECT * FROM sources WHERE file_id=?", (identifier,)).fetchone())
    with db:
        emit(db, "ready", source=source)


def test_committed_ready_events_queue_once_and_cursor_survives_restart(workspace):
    db, *_ = workspace
    record = discover(workspace)
    ready_event(db, record.id)
    observer.reconcile(db)
    assert db.execute("SELECT COUNT(*) FROM knowledge_jobs").fetchone()[0] == 1
    observer.reconcile(db)
    assert db.execute("SELECT COUNT(*) FROM knowledge_jobs").fetchone()[0] == 1
    assert db.execute("SELECT sequence FROM wiki_consumers").fetchone()[0] > 0


def test_new_version_cancels_stale_queued_inventory_then_queues_current(workspace):
    db, root, _, scan, _ = workspace
    record = discover(workspace)
    ready_event(db, record.id)
    observer.reconcile(db)
    (root / "note.txt").write_text("Changed original: 92.")
    scan()
    (identifier,) = scan()
    ingest(db, identifier)
    ready_event(db, identifier)
    observer.reconcile(db)
    observer.reconcile(db)
    rows = db.execute("SELECT state FROM knowledge_jobs ORDER BY rowid").fetchall()
    assert [r[0] for r in rows] == ["cancelled", "queued"]
