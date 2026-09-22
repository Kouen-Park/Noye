"""Tests for the ingestion pipeline.

Unit tests use an in-memory SQLite database, an in-memory Qdrant, and a mocked
Ollama, so the full status progression and every failure path run in
milliseconds. The integration test at the bottom ingests a real PDF through the
real services.
"""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path

import httpx
import pymupdf
import pytest
from qdrant_client import QdrantClient

from app.config import get_settings
from app.db import files as file_store
from app.db.database import connect, init_schema
from app.models.files import FileStatus, FileType
from app.services.indexing import count_chunks as count_vectors
from app.services.indexing import delete_file_chunks, point_id
from app.services import ingestion
from app.services.ingestion import ingest_file

VECTOR_SIZE = get_settings().qdrant_vector_size


@pytest.fixture
def db() -> sqlite3.Connection:
    connection = connect(":memory:")
    init_schema(connection)
    yield connection
    connection.close()


@pytest.fixture
def qdrant() -> QdrantClient:
    client = QdrantClient(":memory:")
    yield client
    client.close()


def write_pdf(path: Path, page_texts: list[str | None]) -> Path:
    document = pymupdf.open()
    for text in page_texts:
        page = document.new_page()
        if text is not None:
            page.insert_textbox(pymupdf.Rect(60, 60, 540, 700), text, fontsize=11)
    document.save(path)
    document.close()
    return path


def sentences(count: int, marker: str = "Sentence") -> str:
    return " ".join(f"{marker} {i} carries some filler words for length." for i in range(count))


def ollama_client(*, fail: bool = False, status: int = 200) -> httpx.Client:
    """A mock Ollama that returns unit vectors, or fails on demand."""

    def handler(request: httpx.Request) -> httpx.Response:
        if fail:
            raise httpx.ConnectError("connection refused", request=request)
        if status != 200:
            return httpx.Response(status, text="upstream error")
        inputs = json.loads(request.content)["input"]
        return httpx.Response(200, json={"embeddings": [[0.1] * VECTOR_SIZE for _ in inputs]})

    return httpx.Client(transport=httpx.MockTransport(handler))


def add_pdf(db: sqlite3.Connection, tmp_path: Path, pages: list[str | None], name="doc.pdf"):
    path = write_pdf(tmp_path / name, pages)
    return file_store.create_file(
        db,
        name=name,
        file_type=FileType.PDF,
        path=str(path),
        size=path.stat().st_size,
    )


# --- happy path --------------------------------------------------------------


def test_successful_ingestion_ends_ready(db, qdrant, tmp_path) -> None:
    record = add_pdf(db, tmp_path, [sentences(30), sentences(30)])

    with ollama_client() as http:
        result = ingest_file(db, record.id, qdrant_client=qdrant, http_client=http)

    assert result.status is FileStatus.READY
    assert result.error is None


def test_counts_are_recorded(db, qdrant, tmp_path) -> None:
    record = add_pdf(db, tmp_path, [sentences(40), sentences(40), sentences(40)])

    with ollama_client() as http:
        result = ingest_file(db, record.id, qdrant_client=qdrant, http_client=http)

    assert result.page_count == 3
    assert result.chunk_count > 0


def test_chunk_rows_carry_provenance_and_vector_ids(db, qdrant, tmp_path) -> None:
    record = add_pdf(db, tmp_path, [sentences(30), sentences(30)])

    with ollama_client() as http:
        ingest_file(db, record.id, qdrant_client=qdrant, http_client=http)

    rows = file_store.list_chunks(db, record.id)
    assert rows
    assert [row.chunk_index for row in rows] == list(range(len(rows)))
    for row in rows:
        assert row.file_id == record.id
        assert row.page_number in (1, 2)
        assert row.content
        # The row must point at the vector actually stored for it.
        assert row.vector_id == point_id(record.id, row.chunk_index)


def test_vectors_and_rows_agree_in_number(db, qdrant, tmp_path) -> None:
    record = add_pdf(db, tmp_path, [sentences(50), sentences(50)])

    with ollama_client() as http:
        result = ingest_file(db, record.id, qdrant_client=qdrant, http_client=http)

    assert count_vectors(file_id=record.id, client=qdrant) == result.chunk_count
    assert file_store.count_chunks(db, record.id) == result.chunk_count


def test_status_passes_through_every_stage(db, qdrant, tmp_path, monkeypatch) -> None:
    record = add_pdf(db, tmp_path, [sentences(30)])
    seen: list[FileStatus] = []
    real_set_status = file_store.set_status

    def recording(connection, file_id, status, **kwargs):
        seen.append(status)
        return real_set_status(connection, file_id, status, **kwargs)

    monkeypatch.setattr(file_store, "set_status", recording)

    with ollama_client() as http:
        ingest_file(db, record.id, qdrant_client=qdrant, http_client=http)

    assert seen == [
        FileStatus.EXTRACTING,
        FileStatus.CHUNKING,
        FileStatus.EMBEDDING,
        FileStatus.READY,
    ]


# --- idempotency -------------------------------------------------------------


def test_reingesting_does_not_duplicate(db, qdrant, tmp_path) -> None:
    record = add_pdf(db, tmp_path, [sentences(40)])

    with ollama_client() as http:
        first = ingest_file(db, record.id, qdrant_client=qdrant, http_client=http)
        second = ingest_file(db, record.id, qdrant_client=qdrant, http_client=http)

    assert second.chunk_count == first.chunk_count
    assert file_store.count_chunks(db, record.id) == first.chunk_count
    assert count_vectors(file_id=record.id, client=qdrant) == first.chunk_count


def test_reingesting_a_shorter_document_drops_stale_vectors(db, qdrant, tmp_path) -> None:
    path = write_pdf(tmp_path / "shrink.pdf", [sentences(60), sentences(60), sentences(60)])
    record = file_store.create_file(
        db, name="shrink.pdf", file_type=FileType.PDF, path=str(path), size=path.stat().st_size
    )
    with ollama_client() as http:
        long_run = ingest_file(db, record.id, qdrant_client=qdrant, http_client=http)

    # Replace the file on disk with a much shorter one and ingest again.
    write_pdf(tmp_path / "shrink.pdf", [sentences(5)])
    with ollama_client() as http:
        short_run = ingest_file(db, record.id, qdrant_client=qdrant, http_client=http)

    assert short_run.chunk_count < long_run.chunk_count
    # Vectors keyed by the old, higher chunk indexes must not survive.
    assert count_vectors(file_id=record.id, client=qdrant) == short_run.chunk_count


# --- failures ----------------------------------------------------------------


def test_missing_file_on_disk_fails_with_a_reason(db, qdrant, tmp_path) -> None:
    record = file_store.create_file(
        db, name="gone.pdf", file_type=FileType.PDF, path=str(tmp_path / "gone.pdf"), size=10
    )

    with ollama_client() as http:
        result = ingest_file(db, record.id, qdrant_client=qdrant, http_client=http)

    assert result.status is FileStatus.FAILED
    assert "File not found" in result.error


def test_corrupt_pdf_fails_with_a_reason(db, qdrant, tmp_path) -> None:
    path = tmp_path / "corrupt.pdf"
    path.write_bytes(b"%PDF-1.7\nnot really a pdf")
    record = file_store.create_file(
        db, name="corrupt.pdf", file_type=FileType.PDF, path=str(path), size=path.stat().st_size
    )

    with ollama_client() as http:
        result = ingest_file(db, record.id, qdrant_client=qdrant, http_client=http)

    assert result.status is FileStatus.FAILED
    assert "Could not open PDF" in result.error


def test_scanned_pdf_fails_with_an_ocr_explanation(db, qdrant, tmp_path) -> None:
    # A PDF whose pages hold no text layer, as a scan would be.
    record = add_pdf(db, tmp_path, [None, None], name="scan.pdf")

    with ollama_client() as http:
        result = ingest_file(db, record.id, qdrant_client=qdrant, http_client=http)

    assert result.status is FileStatus.FAILED
    assert "OCR" in result.error
    assert result.page_count == 2


def test_unreachable_ollama_fails_with_a_reason(db, qdrant, tmp_path) -> None:
    record = add_pdf(db, tmp_path, [sentences(30)])

    with ollama_client(fail=True) as http:
        result = ingest_file(db, record.id, qdrant_client=qdrant, http_client=http)

    assert result.status is FileStatus.FAILED
    assert "Could not reach Ollama" in result.error


def test_embedding_failure_leaves_no_vectors_behind(db, qdrant, tmp_path) -> None:
    record = add_pdf(db, tmp_path, [sentences(40)])

    with ollama_client(fail=True) as http:
        ingest_file(db, record.id, qdrant_client=qdrant, http_client=http)

    # A FAILED file that still had vectors would answer questions with partial
    # content while the library showed it as broken.
    assert count_vectors(file_id=record.id, client=qdrant) == 0
    assert file_store.count_chunks(db, record.id) == 0


def test_failure_after_a_successful_run_clears_the_old_index(db, qdrant, tmp_path) -> None:
    record = add_pdf(db, tmp_path, [sentences(40)], name="flaky.pdf")
    with ollama_client() as http:
        ingest_file(db, record.id, qdrant_client=qdrant, http_client=http)

    with ollama_client(fail=True) as http:
        result = ingest_file(db, record.id, qdrant_client=qdrant, http_client=http)

    assert result.status is FileStatus.FAILED
    assert count_vectors(file_id=record.id, client=qdrant) == 0
    assert file_store.count_chunks(db, record.id) == 0


def test_markdown_is_ingested_without_page_numbers(db, qdrant, tmp_path) -> None:
    path = tmp_path / "notes.md"
    path.write_text("# Notes\n\n" + sentences(60, "Markdown"))
    record = file_store.create_file(
        db, name="notes.md", file_type=FileType.MARKDOWN, path=str(path), size=path.stat().st_size
    )

    with ollama_client() as http:
        result = ingest_file(db, record.id, qdrant_client=qdrant, http_client=http)

    assert result.status is FileStatus.READY
    assert result.chunk_count > 0
    # Pageless format: a page number here would be one a reader could not verify.
    assert all(row.page_number is None for row in file_store.list_chunks(db, record.id))
    # And no page count is reported, since "1 page" would be noise.
    assert result.page_count is None


def test_text_file_is_ingested(db, qdrant, tmp_path) -> None:
    path = tmp_path / "log.txt"
    path.write_text(sentences(40, "Plain"))
    record = file_store.create_file(
        db, name="log.txt", file_type=FileType.TEXT, path=str(path), size=path.stat().st_size
    )

    with ollama_client() as http:
        result = ingest_file(db, record.id, qdrant_client=qdrant, http_client=http)

    assert result.status is FileStatus.READY
    assert count_vectors(file_id=record.id, client=qdrant) == result.chunk_count


def test_korean_markdown_is_ingested(db, qdrant, tmp_path) -> None:
    path = tmp_path / "한글노트.md"
    path.write_text("# 알고리즘 정리\n\n" + "다익스트라는 거리 추정값이 가장 작은 정점을 선택한다. " * 40)
    record = file_store.create_file(
        db, name="한글노트.md", file_type=FileType.MARKDOWN, path=str(path), size=path.stat().st_size
    )

    with ollama_client() as http:
        result = ingest_file(db, record.id, qdrant_client=qdrant, http_client=http)

    assert result.status is FileStatus.READY
    assert "다익스트라" in file_store.list_chunks(db, record.id)[0].content


def test_whitespace_only_text_file_fails_without_mentioning_ocr(db, qdrant, tmp_path) -> None:
    path = tmp_path / "blank.txt"
    path.write_text("   \n\n\t  \n")
    record = file_store.create_file(
        db, name="blank.txt", file_type=FileType.TEXT, path=str(path), size=path.stat().st_size
    )

    with ollama_client() as http:
        result = ingest_file(db, record.id, qdrant_client=qdrant, http_client=http)

    assert result.status is FileStatus.FAILED
    assert "no text to index" in result.error
    # OCR is irrelevant to a text file; the message must not suggest it.
    assert "OCR" not in result.error


def test_non_utf8_text_file_fails_with_guidance(db, qdrant, tmp_path) -> None:
    path = tmp_path / "legacy.txt"
    path.write_bytes("다익스트라 알고리즘".encode("cp949"))
    record = file_store.create_file(
        db, name="legacy.txt", file_type=FileType.TEXT, path=str(path), size=path.stat().st_size
    )

    with ollama_client() as http:
        result = ingest_file(db, record.id, qdrant_client=qdrant, http_client=http)

    assert result.status is FileStatus.FAILED
    assert "not valid UTF-8" in result.error


def test_failure_does_not_touch_another_file(db, qdrant, tmp_path) -> None:
    good = add_pdf(db, tmp_path, [sentences(30)], name="good.pdf")
    bad = add_pdf(db, tmp_path, [None], name="bad.pdf")

    with ollama_client() as http:
        ingest_file(db, good.id, qdrant_client=qdrant, http_client=http)
        ingest_file(db, bad.id, qdrant_client=qdrant, http_client=http)

    assert file_store.get_file(db, good.id).status is FileStatus.READY
    assert count_vectors(file_id=good.id, client=qdrant) > 0


def test_unknown_file_id_raises(db, qdrant) -> None:
    with pytest.raises(file_store.FileRecordNotFound):
        ingest_file(db, "no-such-file", qdrant_client=qdrant)


# --- integration: real services ---------------------------------------------


def service_is_up(url: str) -> bool:
    try:
        return httpx.get(url, timeout=2.0).status_code == 200
    except httpx.RequestError:
        return False


requires_services = pytest.mark.skipif(
    not (
        service_is_up(f"{get_settings().ollama_base_url}/api/version")
        and service_is_up(f"{get_settings().qdrant_url}/")
    ),
    reason="Ollama or Qdrant is not running",
)

INTEGRATION_FILE_NAME = "integration-ingestion.pdf"


@requires_services
def test_real_ingestion_makes_a_document_searchable_and_citable(db, tmp_path) -> None:
    """The whole Phase 2 point: upload a file, then ask about it."""
    from app.services.citations import build_citations
    from app.services.generation import answer_question

    path = write_pdf(
        tmp_path / INTEGRATION_FILE_NAME,
        [
            "Chapter one introduces graphs, vertices and edges in general terms.",
            "Dijkstra's algorithm always selects the unvisited vertex whose "
            "distance estimate is smallest, drawing it from a priority queue.",
            "Chapter three covers unrelated material about sorting networks.",
        ],
    )
    record = file_store.create_file(
        db,
        name=INTEGRATION_FILE_NAME,
        file_type=FileType.PDF,
        path=str(path),
        size=path.stat().st_size,
    )
    client = QdrantClient(url=get_settings().qdrant_url)
    try:
        result = ingest_file(db, record.id, qdrant_client=client)
        assert result.status is FileStatus.READY, result.error
        assert result.page_count == 3

        answer = answer_question(
            "How does Dijkstra choose the next vertex?",
            file_ids=[record.id],
            qdrant_client=client,
        )
        citations = build_citations(answer.sources, file_names=file_store.file_names(db))

        assert answer.is_grounded
        # The fact lives only on page 2, and the citation now shows a filename
        # rather than a UUID because the file row supplies it.
        assert citations[0].page_number == 2
        assert citations[0].label == f"{INTEGRATION_FILE_NAME} — page 2"
    finally:
        delete_file_chunks(record.id, client=client)
        client.close()


# --- one pipeline per file ---------------------------------------------------


def test_a_file_is_not_in_flight_when_idle(db, tmp_path) -> None:
    record = add_pdf(db, tmp_path, ["Only page."])
    assert ingestion.is_ingesting(record.id) is False


def test_a_second_run_on_a_busy_file_is_refused(db, qdrant, tmp_path, monkeypatch) -> None:
    """Two pipelines on one file would interleave writes to the same rows."""
    record = add_pdf(db, tmp_path, ["Dijkstra picks the smallest estimate."])

    observed: list[bool] = []
    real_chunk = ingestion._chunk

    def chunk_and_reenter(connection, rec, pages):
        # Mid-pipeline the file must report busy, and a nested run must be
        # refused rather than allowed to interleave.
        observed.append(ingestion.is_ingesting(rec.id))
        with pytest.raises(ingestion.AlreadyIngesting):
            ingest_file(
                connection, rec.id, qdrant_client=qdrant, http_client=ollama_client()
            )
        return real_chunk(connection, rec, pages)

    monkeypatch.setattr(ingestion, "_chunk", chunk_and_reenter)
    ingest_file(db, record.id, qdrant_client=qdrant, http_client=ollama_client())

    assert observed == [True]


def test_the_in_flight_slot_is_released_after_a_failure(db, qdrant, tmp_path) -> None:
    """A failed run must not leave the file permanently marked busy."""
    record = add_pdf(db, tmp_path, [None])  # scanned: no extractable text
    result = ingest_file(
        db, record.id, qdrant_client=qdrant, http_client=ollama_client()
    )
    assert result.status is FileStatus.FAILED
    assert ingestion.is_ingesting(record.id) is False


def test_finished_run_does_not_release_a_new_reservation(db, qdrant, tmp_path, monkeypatch) -> None:
    record = add_pdf(db, tmp_path, [sentences(8)])
    real_release = ingestion._release

    def claim_before_finally_releases(file_id, cancellation):
        # READY frees the old slot before finally runs. Another request can
        # claim it in that gap, and the old run must leave the new claim alone.
        ingestion.reserve_ingestion(file_id)
        real_release(file_id, cancellation)

    monkeypatch.setattr(ingestion, "_release", claim_before_finally_releases)
    try:
        result = ingest_file(db, record.id, qdrant_client=qdrant, http_client=ollama_client())
        assert result.status is FileStatus.READY
        assert ingestion.is_ingesting(record.id)
    finally:
        ingestion.release_file(record.id)


def test_cancellation_during_embedding_never_indexes(db, qdrant, tmp_path, monkeypatch) -> None:
    record = add_pdf(db, tmp_path, [sentences(8)])
    indexed = []
    monkeypatch.setattr(ingestion, "delete_file_chunks", lambda *args, **kwargs: None)
    monkeypatch.setattr(ingestion, "index_chunks", lambda *args, **kwargs: indexed.append(True))

    def cancel_while_embedding(chunks, *, client):
        assert ingestion.cancel_ingestion(record.id)
        return [[0.0] * 4 for _ in chunks]

    monkeypatch.setattr(ingestion, "embed_chunks", cancel_while_embedding)
    result = ingest_file(db, record.id, qdrant_client=qdrant, http_client=ollama_client())

    assert result.status is FileStatus.FAILED
    assert result.error == "Processing was cancelled."
    assert indexed == []
    assert ingestion.is_ingesting(record.id) is False


def test_failure_clears_the_chunk_count_it_no_longer_has(db, qdrant, tmp_path) -> None:
    """A file that chunked and then failed must not advertise those passages."""
    record = add_pdf(db, tmp_path, [sentences(8)])
    result = ingest_file(
        db,
        record.id,
        qdrant_client=qdrant,
        http_client=ollama_client(fail=True),  # dies during embedding
    )

    assert result.status is FileStatus.FAILED
    assert result.chunk_count == 0
    assert file_store.count_chunks(db, record.id) == 0
    # The pages really were read, so that number stays true.
    assert result.page_count == 1
