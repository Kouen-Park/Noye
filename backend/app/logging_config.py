"""Logging configuration.

Noye had no logging at all until now, which was survivable while every failure
was reproducible by hand. It stops being survivable once the index can be stale,
a duplicate can be refused and a model can change underneath a library: those
failures depend on state built up over weeks, and "it said it failed" is not
enough to tell which of them happened.

What may not be logged
----------------------
**No file contents, no chunk text, no question, no answer, no document body.**

This is the rule the module exists to hold, not a preference. Noye's whole claim
is that a private library stays on the machine it was indexed on, and a log file
is the one place that content would be written *outside* the files the user chose
to put there — a plain-text file, unencrypted, easy to forget, and the first thing
anyone pastes into a bug report.

A comment asking for that would not survive a hurried afternoon, so
``test_logging.py`` asserts it instead: it drives the real pipeline with sentinel
text and fails if the sentinel reaches a handler.

What must be logged
-------------------
The pipeline's decisions and every failure's cause. The ingestion error already
reaches SQLite for the UI to show; this is for whoever is debugging, so it carries
what the UI deliberately withholds — stage timings, exception types, tracebacks,
which model answered, how many chunks and pages, which Qdrant call failed.

Identifiers are fine and are the point: a file id, a chunk count, a page count, a
model name, a collection name, an elapsed time. None of them is the user's text.

Shape
-----
Standard library ``logging`` with a plain line formatter. No dependency, and
greppable, which is what a single-user local application actually needs; if this
ever has to be machine-parsed, the formatter is the only thing to change.

Two handlers: stderr, because that is where a developer running ``uvicorn`` looks,
and a rotating file under ``data/logs/`` so a failure that happened overnight is
still there in the morning. Rotation is capped rather than unbounded — a log that
fills a disk is its own outage.
"""

from __future__ import annotations

import logging
import logging.handlers
import sys
import time
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

from app.config import PROJECT_ROOT, get_settings

#: Every Noye logger hangs off this name, so configuration touches Noye's own
#: output and leaves uvicorn, httpx and qdrant-client to their own defaults.
#: Turning on Noye's DEBUG must not turn on httpx's request-by-request logging,
#: which would defeat the whole content rule by logging request bodies.
ROOT_LOGGER = "noye"

#: 5 files x 2 MB. Enough to hold a few days of a single user's ingestion history,
#: bounded so it cannot become the reason a disk fills.
MAX_BYTES = 2 * 1024 * 1024
BACKUP_COUNT = 5

_configured = False


def log_directory() -> Path:
    """Where the log file lives. Beside the database and the sources, not in /tmp."""
    return PROJECT_ROOT / "data" / "logs"


def get_logger(name: str) -> logging.Logger:
    """A logger under Noye's namespace.

    Callers pass their module's own suffix (``"ingestion"``, ``"embeddings"``), so
    a line says which part of the pipeline produced it and a developer can raise
    the level on one area without raising it everywhere.
    """
    return logging.getLogger(f"{ROOT_LOGGER}.{name}")


def configure_logging(*, force: bool = False) -> logging.Logger:
    """Attach Noye's handlers. Idempotent.

    Called once at application startup. The idempotence is not decoration: the
    tests import the app repeatedly and uvicorn's reloader re-imports modules, and
    each of those would otherwise add another pair of handlers and multiply every
    line.
    """
    global _configured
    logger = logging.getLogger(ROOT_LOGGER)

    if _configured and not force:
        return logger

    for handler in list(logger.handlers):
        logger.removeHandler(handler)
        handler.close()

    settings = get_settings()
    level = getattr(logging, settings.log_level.upper(), logging.INFO)
    logger.setLevel(level)

    # Noye's lines are Noye's. Without this, a line also travels to the root
    # logger, which uvicorn configures with its own format, and every entry
    # appears twice in different shapes.
    logger.propagate = False

    formatter = logging.Formatter(
        fmt="%(asctime)s %(levelname)-7s %(name)-22s %(message)s",
        datefmt="%Y-%m-%dT%H:%M:%S",
    )

    stream = logging.StreamHandler(sys.stderr)
    stream.setFormatter(formatter)
    logger.addHandler(stream)

    if settings.log_to_file:
        try:
            directory = log_directory()
            directory.mkdir(parents=True, exist_ok=True)
            file_handler = logging.handlers.RotatingFileHandler(
                directory / "noye.log",
                maxBytes=MAX_BYTES,
                backupCount=BACKUP_COUNT,
                encoding="utf-8",
            )
            file_handler.setFormatter(formatter)
            logger.addHandler(file_handler)
        except OSError as exc:
            # A read-only or full disk must not stop Noye from serving. Say so on
            # stderr, which is already attached, and carry on.
            logger.warning("File logging unavailable, continuing on stderr: %s", exc)

    _configured = True
    return logger


@contextmanager
def timed(logger: logging.Logger, what: str, **fields: object) -> Iterator[None]:
    """Log how long something took, and log it even when it raised.

    Duration is the field that makes an ingestion log worth keeping: a stage that
    failed and a stage that took four minutes look identical in a status column,
    and only one of them is a bug in Noye.

    ``fields`` are identifiers — a file id, a chunk count, a model name. Never
    text the user wrote.
    """
    started = time.monotonic()
    extra = " ".join(f"{key}={value}" for key, value in fields.items())
    suffix = f" {extra}" if extra else ""
    try:
        yield
    except BaseException as exc:
        elapsed = time.monotonic() - started
        logger.warning(
            "%s failed after %.2fs%s error=%s: %s",
            what,
            elapsed,
            suffix,
            type(exc).__name__,
            exc,
        )
        raise
    else:
        elapsed = time.monotonic() - started
        logger.info("%s in %.2fs%s", what, elapsed, suffix)
