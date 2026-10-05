"""Single-process snapshot boundary shared by requests and library maintenance."""

import threading
from contextlib import contextmanager

from app.services import ingestion

_lock = threading.Lock()
_requests = 0
_snapshot = False


class WorkspaceBusy(RuntimeError):
    pass


@contextmanager
def request_access():
    global _requests
    with _lock:
        if _snapshot:
            raise WorkspaceBusy("A workspace backup is in progress. Try again when it finishes.")
        _requests += 1
    try:
        yield
    finally:
        with _lock:
            _requests -= 1


@contextmanager
def snapshot_access():
    global _snapshot
    with _lock:
        if _snapshot or _requests:
            raise WorkspaceBusy("Finish active requests before backing up the workspace.")
        _snapshot = True
    reserved = False
    try:
        ingestion.begin_rebuild()
        reserved = True
        ingestion.require_idle_library()
        yield
    finally:
        if reserved:
            ingestion.end_rebuild()
        with _lock:
            _snapshot = False
