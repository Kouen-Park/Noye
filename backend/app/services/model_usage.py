"""Coordinate Noye's synchronous inference with asynchronous model deletion."""

from collections import Counter
from contextlib import contextmanager
from threading import BoundedSemaphore, Lock

from fastapi import HTTPException

lock = Lock()
active = Counter()
deleting = set()
slots = BoundedSemaphore(1)
WAIT_SECONDS = 30.0


class ModelBusyError(RuntimeError):
    pass


def canonical(model):
    return model if ":" in model else f"{model}:latest"


@contextmanager
def inference(model):
    name = canonical(model)
    with lock:
        if name in deleting:
            raise ModelBusyError("This model is being deleted. Choose another local model.")
        active[name] += 1
    acquired = False
    try:
        acquired = slots.acquire(timeout=WAIT_SECONDS)
        if not acquired:
            raise ModelBusyError(
                "Local inference is busy. Wait for processing to finish and retry."
            )
        yield
    finally:
        if acquired:
            slots.release()
        with lock:
            active[name] -= 1
            if not active[name]:
                del active[name]


@contextmanager
def deletion(model):
    name = canonical(model)
    with lock:
        from app.config import get_settings

        settings = get_settings()
        if name in {canonical(settings.ollama_model), canonical(settings.ollama_embedding_model)}:
            raise HTTPException(409, "The selected generation and embedding models are protected.")
        if active[name] or name in deleting:
            raise HTTPException(409, "This model is in use by Noye. Wait for generation to finish.")
        deleting.add(name)
    try:
        yield
    finally:
        with lock:
            deleting.discard(name)
