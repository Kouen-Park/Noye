import pytest

from app.db import wiki
from app.db.database import connect, init_schema


@pytest.fixture
def db():
    connection = connect(":memory:")
    init_schema(connection)
    wiki.install(connection)
    connection.commit()
    yield connection
    connection.close()


def write(db, page, content, expected=None, origin="generated"):
    return wiki.write_revision(db, page["id"], title=page["title"], content=content,
                               metadata={}, evidence=[], expected=expected, origin=origin)


def test_idempotent_schema_and_stable_identity(db):
    wiki.install(db)
    db.commit()
    first = wiki.ensure_page(db, "source", "source:stable", "Original")
    assert wiki.ensure_page(db, "source", "source:stable", "Renamed")["id"] == first["id"]


def test_user_edit_and_racing_refresh_are_preserved(db):
    page = wiki.ensure_page(db, "source", "source:stable", "Notes")
    first = write(db, page, "Generated")
    edited = write(db, page, "User's 한국어 edit", first["id"], "user")
    proposal = write(db, page, "New model summary", first["id"])
    assert proposal["origin"] == "proposal"
    assert wiki.page(db, page["id"])["current_revision"] == edited["id"]
    assert wiki.revision(db, edited["id"])["content"] == "User's 한국어 edit"
    proposal2 = write(db, page, "Another summary", edited["id"])
    assert proposal2["origin"] == "proposal"
    with pytest.raises(ValueError, match="changed"):
        write(db, page, "stale edit", first["id"], "user")
    assert len(wiki.revisions(db, page["id"])) == 4


def test_index_revision_identity_changes_independently(db):
    page = wiki.ensure_page(db, "source", "source:x", "Notes")
    first = write(db, page, "One")
    fingerprint = db.execute("SELECT fingerprint FROM wiki_index").fetchone()[0]
    write(db, page, "Two", first["id"])
    assert db.execute("SELECT fingerprint FROM wiki_index").fetchone()[0] != fingerprint


def test_source_deletion_cannot_cascade_wiki(db):
    page = wiki.ensure_page(db, "source", "source:deleted", "Historical notes")
    write(db, page, "Saved text")
    # No dependency on live files, unlike the ingestion-only job schema.
    db.execute("DELETE FROM files")
    db.commit()
    assert wiki.page(db, page["id"])["current_revision"] is not None
