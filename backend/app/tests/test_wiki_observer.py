from unittest.mock import patch

from app.services import knowledge_jobs
from app.services.folders import emit, update_root
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


def test_resume_queues_ready_sources_skipped_while_paused(workspace):
    db, _, root_id, *_ = workspace
    record = discover(workspace)
    update_root(db, root_id, processing=False)
    ready_event(db, record.id)
    observer.reconcile(db)
    assert db.execute("SELECT COUNT(*) FROM knowledge_jobs").fetchone()[0] == 0
    update_root(db, root_id, processing=True)
    observer.reconcile(db)
    observer.reconcile(db)
    assert db.execute("SELECT COUNT(*) FROM knowledge_jobs").fetchone()[0] == 1
    assert db.execute("SELECT status FROM files WHERE id=?", (record.id,)).fetchone()[0] == "READY"


def test_deleted_source_does_not_block_later_ready_events(workspace):
    db, *_ = workspace
    with db:
        emit(db, "ready", source={"file_id": "previously-removed-upload"})
    retained = discover(workspace, "retained.txt")
    observer.reconcile(db)
    assert [r[0] for r in db.execute("SELECT subject_id FROM knowledge_jobs")] == [retained.id]


def test_same_version_cancellation_leaves_ready_event_pending(workspace):
    db, *_ = workspace
    record = discover(workspace)
    ready_event(db, record.id)
    observer.reconcile(db)
    old = db.execute("SELECT id FROM knowledge_jobs").fetchone()[0]
    with db:
        db.execute("UPDATE knowledge_jobs SET state='running' WHERE id=?", (old,))
    knowledge_jobs.cancel(db, old)
    cursor = db.execute("SELECT sequence FROM wiki_consumers WHERE name='sources'").fetchone()[0]
    ready_event(db, record.id)
    observer.reconcile(db)
    assert (
        db.execute("SELECT sequence FROM wiki_consumers WHERE name='sources'").fetchone()[0]
        == cursor
    )
    with db:
        db.execute("UPDATE knowledge_jobs SET state='cancelled' WHERE id=?", (old,))
    observer.reconcile(db)
    assert [r[0] for r in db.execute("SELECT state FROM knowledge_jobs ORDER BY rowid")] == [
        "cancelled",
        "queued",
    ]


def test_partial_resume_progress_does_not_repeat_completed_subject(workspace):
    db, _, root_id, *_ = workspace
    first = discover(workspace, "one.txt")
    second = discover(workspace, "two.txt")
    with db:
        db.execute(
            "INSERT INTO wiki_consumers VALUES ('sources',?)",
            (max(e["sequence"] for e in observer.sources.catalog(db).changes()),),
        )
    # Control order so a later cancelling task blocks the root after one queued subject.
    original = observer.sources.catalog

    class OrderedCatalog:
        def __init__(self, connection):
            self.real = original(connection)

        def __getattr__(self, name):
            return getattr(self.real, name)

        def list_sources(self, scope):
            return sorted(self.real.list_sources(scope), key=lambda r: r["source_id"] != first.id)

    ready_event(db, second.id)
    observer.reconcile(db)
    old = db.execute("SELECT id FROM knowledge_jobs WHERE subject_id=?", (second.id,)).fetchone()[0]
    with db:
        db.execute("UPDATE knowledge_jobs SET state='running' WHERE id=?", (old,))
    update_root(db, root_id, processing=False)
    observer.reconcile(db)
    assert knowledge_jobs.get(db, old)["state"] == "cancelling"
    update_root(db, root_id, processing=True)
    with patch.object(observer.sources, "catalog", OrderedCatalog):
        observer.reconcile(db)
        new = db.execute(
            "SELECT id FROM knowledge_jobs WHERE subject_id=?", (first.id,)
        ).fetchone()[0]
        with db:
            db.execute("UPDATE knowledge_jobs SET state='complete' WHERE id=?", (new,))
            db.execute("UPDATE knowledge_jobs SET state='cancelled' WHERE id=?", (old,))
        observer.reconcile(db)
    assert (
        db.execute(
            "SELECT COUNT(*) FROM knowledge_jobs WHERE subject_id=?", (first.id,)
        ).fetchone()[0]
        == 1
    )
    assert (
        db.execute(
            "SELECT COUNT(*) FROM knowledge_jobs WHERE subject_id=?", (second.id,)
        ).fetchone()[0]
        == 2
    )
