"""The maintenance guard protects planning across request threads."""

from concurrent.futures import ThreadPoolExecutor
from threading import Event

import pytest

from app.services import ingestion


def test_no_new_operation_can_enter_while_another_thread_plans():
    entered = Event()
    finish = Event()

    def plan():
        ingestion.begin_rebuild()
        try:
            entered.set()
            assert finish.wait(timeout=5)
        finally:
            ingestion.end_rebuild()

    with ThreadPoolExecutor(max_workers=1) as executor:
        future = executor.submit(plan)
        assert entered.wait(timeout=5)
        try:
            for operation in (
                ingestion.reserve_ingestion, ingestion.reserve_delete, ingestion.begin_rebuild
            ):
                with pytest.raises(ingestion.MaintenanceBusy):
                    if operation is ingestion.begin_rebuild:
                        operation()
                    else:
                        operation("new-source")
        finally:
            finish.set()
        future.result(timeout=5)
    ingestion.reserve_delete("new-source")
    ingestion.release_file("new-source")
