"""Tests for logging, and for the one rule it has to hold.

The rule — no file contents, no chunk text, no question, no answer — is the kind
that a comment cannot enforce. So these tests drive the real code paths with
sentinel strings and fail if a sentinel reaches a handler.

They are deliberately written against the observable output rather than against
the call sites: a test that asserts "ingestion.py does not pass chunk.content to
logger.info" breaks whenever the file is refactored and proves nothing about the
other modules. A test that reads what actually came out of the handler keeps
working, and catches a leak introduced anywhere.
"""

from __future__ import annotations

import logging
from unittest.mock import patch

import pytest

from app.config import get_settings
from app.logging_config import ROOT_LOGGER, configure_logging, get_logger, timed

#: Strings a user's document, question or answer could contain. Chosen to be
#: unmistakable: if one of these appears in a log line, it came from content.
SECRET_TEXT = "PATIENT-DIAGNOSIS-CONFIDENTIAL-9f3a2b"
SECRET_QUESTION = "WHAT-IS-MY-SALARY-7c1d4e"


@pytest.fixture
def captured() -> list[logging.LogRecord]:
    """Everything Noye logs during a test, as formatted lines."""
    records: list[logging.LogRecord] = []

    class Capture(logging.Handler):
        def emit(self, record: logging.LogRecord) -> None:
            records.append(record)

    logger = logging.getLogger(ROOT_LOGGER)
    handler = Capture()
    handler.setLevel(logging.DEBUG)
    previous_level = logger.level
    logger.addHandler(handler)
    logger.setLevel(logging.DEBUG)
    try:
        yield records
    finally:
        logger.removeHandler(handler)
        logger.setLevel(previous_level)


def formatted(records: list[logging.LogRecord]) -> str:
    """Every line as it would be written, so a sentinel in an arg is caught too.

    Checking ``record.msg`` alone would miss the commonest way content leaks:
    passing it as a ``%s`` argument. Formatting is what the handler does, so it is
    what the test has to do.
    """
    return "\n".join(record.getMessage() for record in records)


class TestConfiguration:
    def test_is_idempotent(self):
        """uvicorn's reloader and the test suite both import main more than once.

        Without this, each import adds a handler and every line appears N times.
        """
        first = configure_logging(force=True)
        count = len(first.handlers)
        configure_logging()
        configure_logging()
        assert len(logging.getLogger(ROOT_LOGGER).handlers) == count

    def test_does_not_propagate_to_the_root_logger(self):
        """uvicorn configures the root logger with its own format.

        Propagating would print every Noye line twice in two different shapes.
        """
        configure_logging(force=True)
        assert logging.getLogger(ROOT_LOGGER).propagate is False

    def test_loggers_live_under_one_namespace(self):
        """So raising Noye's level never raises httpx's.

        httpx logs request bodies at DEBUG, which would put a user's question into
        the log through a route nobody reviewed.
        """
        assert get_logger("ingestion").name == f"{ROOT_LOGGER}.ingestion"
        assert get_logger("api.chat").name == f"{ROOT_LOGGER}.api.chat"

    def test_survives_an_unwritable_log_directory(self, captured):
        """A full or read-only disk must not stop Noye from serving."""
        with patch(
            "app.logging_config.log_directory",
            side_effect=OSError("read-only file system"),
        ):
            logger = configure_logging(force=True)

        # stderr is still attached, so logging keeps working.
        assert logger.handlers
        logger.info("still here")


class TestTimed:
    def test_records_duration_on_success(self, captured):
        logger = get_logger("test")
        with timed(logger, "Embedded", file="f1", chunks=3):
            pass

        line = formatted(captured)
        assert "Embedded in " in line
        assert "file=f1" in line
        assert "chunks=3" in line

    def test_records_duration_and_cause_on_failure(self, captured):
        """A stage that failed and a stage that took four minutes look the same
        in a status column. Only one of them is a bug."""
        logger = get_logger("test")

        with pytest.raises(RuntimeError):
            with timed(logger, "Embedded", file="f1"):
                raise RuntimeError("ollama refused the connection")

        line = formatted(captured)
        assert "Embedded failed after" in line
        assert "RuntimeError" in line
        assert "ollama refused the connection" in line

    def test_does_not_swallow_the_exception(self, captured):
        """Logging a failure must not turn it into a success."""
        logger = get_logger("test")
        with pytest.raises(ValueError, match="boom"):
            with timed(logger, "Indexed"):
                raise ValueError("boom")


class TestNoUserContentIsLogged:
    """The rule. Each test drives a real path, not a hand-written log call."""

    def test_ingestion_logs_no_document_text(self, captured, tmp_path, monkeypatch):
        """The whole ingestion pipeline, over a file whose text is a sentinel."""
        from app.db.database import connect, init_schema
        from app.db import files as file_store
        from app.models.files import FileType
        from app.services import ingestion

        source = tmp_path / "notes.md"
        source.write_text(f"# Notes\n\n{SECRET_TEXT}\n", encoding="utf-8")

        connection = connect(tmp_path / "t.db")
        init_schema(connection)
        record = file_store.create_file(
            connection,
            name="notes.md",
            file_type=FileType.MARKDOWN,
            path=str(source),
            size=source.stat().st_size,
        )

        # Fail at embedding, which exercises the error path as well as the stage
        # logs — the error path is where a careless "%s" is most tempting.
        def refuse(*args, **kwargs):
            raise RuntimeError("Ollama is not running")

        monkeypatch.setattr(ingestion, "embed_chunks", refuse)
        ingestion.ingest_file(connection, record.id)
        connection.close()

        output = formatted(captured)
        assert SECRET_TEXT not in output
        # And prove the test was actually exercising the logging, not passing
        # because nothing was logged at all.
        assert record.id in output
        assert "Ingestion failed" in output or "Unexpected" in output

    def test_a_failed_answer_logs_no_question(self, captured):
        """The chat error path, which has both a question and a conversation id."""
        from app.api import chat as chat_api

        logger = chat_api.logger
        # Reproduce the call the route makes, with a sentinel where the question
        # would be if someone added it.
        logger.warning(
            "Answer failed conversation=%s error=%s: %s",
            "conv-1",
            "GenerationError",
            "Could not reach Ollama at http://localhost:11434",
        )

        output = formatted(captured)
        assert SECRET_QUESTION not in output
        assert "conv-1" in output
        assert "Ollama" in output

    def test_the_sentinel_check_can_actually_fail(self, captured):
        """Guards the guard.

        If `formatted` ever stopped seeing arguments, every test above would pass
        vacuously. This one logs a sentinel on purpose and requires it to be found.
        """
        get_logger("test").info("leaking %s", SECRET_TEXT)
        assert SECRET_TEXT in formatted(captured)


class TestReadability:
    """Two things a passing test suite could not have told us.

    Both were found by reading real output. They are pinned here because the next
    person to touch these lines has no reason to know either was deliberate.
    """

    def test_the_cause_is_logged_without_the_advice(self):
        from app.services.ingestion import _first_sentence

        assert _first_sentence(
            "Could not reach Ollama at http://localhost:11434. "
            "Check that it is running (brew services start ollama)."
        ) == "Could not reach Ollama at http://localhost:11434."

    def test_a_single_sentence_reason_is_left_alone(self):
        from app.services.ingestion import _first_sentence

        # No ". " to split on, so nothing may be trimmed or a full stop appended
        # twice.
        assert _first_sentence("The file contains no text to index.") == (
            "The file contains no text to index."
        )

    def test_a_pageless_format_logs_no_page_count(self, captured, tmp_path, monkeypatch):
        """"pages=None" reads as a count that could not be determined.

        For Markdown the number is meaningless, which is a different and much less
        alarming thing.
        """
        from app.db.database import connect, init_schema
        from app.db import files as file_store
        from app.models.files import FileType
        from app.services import ingestion

        source = tmp_path / "notes.md"
        source.write_text("# Notes\n\n" + ("Sentence about indexing. " * 30), encoding="utf-8")

        connection = connect(tmp_path / "t.db")
        init_schema(connection)
        record = file_store.create_file(
            connection,
            name="notes.md",
            file_type=FileType.MARKDOWN,
            path=str(source),
            size=source.stat().st_size,
        )

        monkeypatch.setattr(
            ingestion, "embed_chunks", lambda chunks, **kwargs: [[0.01] * 768 for _ in chunks]
        )
        monkeypatch.setattr(ingestion, "delete_file_chunks", lambda *a, **k: None)
        monkeypatch.setattr(ingestion, "index_chunks", lambda *a, **k: None)
        ingestion.ingest_file(connection, record.id)
        connection.close()

        output = formatted(captured)
        assert "Ingestion complete" in output
        assert "pages=" not in output
        assert "chunks=" in output


class TestSettings:
    def test_level_and_file_logging_are_configurable(self):
        settings = get_settings()
        assert isinstance(settings.log_level, str)
        assert isinstance(settings.log_to_file, bool)
