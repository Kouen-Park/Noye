"""Real durable jobs, with stable request/artifact identity and explicit retry."""

from threading import Lock

from app.db import conversations
from app.db import source_documents as store
from app.db.wiki import now
from app.models.conversations import Role
from app.models.wiki import WikiScope
from app.services import knowledge_jobs
from app.services.source_catalog import SourceCatalog
from app.services.source_documents import pipeline


def register():
    knowledge_jobs.register("source_document", handler)


def handler(context, payload):
    try:
        return pipeline.generate(context)
    except pipeline.ClarificationRequired as exc:
        store.save_request(context.connection, context.job["subject_id"], clarification=str(exc))
        raise
    except pipeline.local.DocumentError:
        # Valid JSON with invalid evidence must not become a permanently failing retry cache.
        store.save_request(context.connection, context.job["subject_id"], cache={})
        raise


_enqueue_lock = Lock()


def enqueue(connection, request):
    with _enqueue_lock:
        return _create_request(connection, request)


def _create_request(connection, request):
    try:
        existing = store.request(connection, request.request_id)
    except LookupError:
        existing = None
    if existing:
        original = existing["request"]
        if any(
            original[key] != getattr(request, key) for key in ("instruction", "inventory_mode")
        ) or (original.get("submitted_scope", original["scope"]) != request.scope.model_dump()):
            raise ValueError("This request ID already belongs to a different document request.")
        row = connection.execute(
            "SELECT id FROM knowledge_jobs WHERE kind='source_document' AND "
            "subject_id=? ORDER BY rowid DESC LIMIT 1",
            (request.request_id,),
        ).fetchone()
        if row:
            return knowledge_jobs.get(connection, row[0])
        return _enqueue(connection, existing)

    submitted_scope = request.scope.model_dump()
    # Persist the original chat intent, without creating or using an assistant answer.
    if request.conversation_id:
        conversation = conversations.read_conversation(connection, request.conversation_id)
        if conversation.source_scope is not None:
            selected = {
                s["source_id"] for s in SourceCatalog(connection).freeze(request.scope.model_dump())
            }
            ids = sorted(selected & set(conversation.source_scope))
            request.scope = (
                WikiScope(mode="chosen", source_ids=ids) if ids else WikiScope(mode="empty")
            )
    else:
        conversation = conversations.create_conversation(
            connection, first_question=request.instruction
        )
        request.conversation_id = conversation.id
        if request.scope.mode != "all":
            ids = [
                s["source_id"] for s in SourceCatalog(connection).freeze(request.scope.model_dump())
            ]
            conversations.set_source_scope(connection, conversation.id, ids)
    # Context is limited to actual user turns. It is explicitly labelled intent-only.
    request.intent_context = [m.content for m in conversation.messages if m.role is Role.USER][-6:]
    if any(len(value) > 4000 for value in request.intent_context):
        raise ValueError(
            "A recent user turn is too long for intent resolution. Start a new conversation."
        )
    conversations.add_message(
        connection, conversation.id, role=Role.USER, content=request.instruction
    )
    manifest = SourceCatalog(connection).freeze(request.scope.model_dump())
    for identifier in request.scope.source_ids:
        if not any(s["source_id"] == identifier for s in manifest):
            manifest.append(
                {
                    "source_id": identifier,
                    "root_id": None,
                    "relative_path": identifier,
                    "version": None,
                    "availability": "missing",
                    "processing_state": "MISSING",
                }
            )
    timestamp = now()
    with connection:
        connection.execute(
            "INSERT INTO source_document_requests(id,request_json,manifest_json,"
            "created_at,updated_at) VALUES(?,?,?,?,?)",
            (
                request.request_id,
                store.encode({**request.model_dump(), "submitted_scope": submitted_scope}),
                store.encode(manifest),
                timestamp,
                timestamp,
            ),
        )
    return _enqueue(connection, store.request(connection, request.request_id))


def _enqueue(connection, request):
    return knowledge_jobs.enqueue(
        connection,
        kind="source_document",
        subject_id=request["id"],
        payload={"request_id": request["id"]},
        scope=request["request"]["scope"],
        manifest=request["manifest"],
        dedupe_key="source_document:" + request["id"],
    )


def public_request(connection, identifier):
    request = store.request(connection, identifier)
    return {key: value for key, value in request.items() if key != "cache"}
