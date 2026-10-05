"""Portable provenance from saved evidence, independent of the live index."""

import re
import sqlite3

from app.db import files as file_store
from app.models.conversations import MessageCitation
from app.services.integrity import hash_file


def original_status(db: sqlite3.Connection, citation: MessageCitation) -> str:
    try:
        record = file_store.get_file(db, citation.file_id)
    except file_store.FileRecordNotFound:
        return "missing"
    digest = hash_file(record.path)
    if digest is None:
        return "missing"
    if citation.source_hash is None:
        return "unknown"
    return "unchanged" if digest == citation.source_hash else "changed"


def provenance_markdown(citations: list[MessageCitation]) -> str:
    if not citations:
        return ""
    parts = ["## Provenance", "Evidence saved with the first draft, from passages "
             "consulted for its source answer. "
             "These do not validate later edits or every generated claim."]
    for citation in citations:
        # Escape source labels and render excerpts literally, including Markdown/HTML.
        label = re.sub(r"([\\`*_{}\[\]()<>#!|])", r"\\\1", " ".join(citation.label.split()))
        parts.append(f"> {label}\n> Source SHA-256: {citation.source_hash or 'unknown (legacy)'}"
                     f"\n> Index fingerprint: {citation.index_fingerprint or 'unknown (legacy)'}"
                     f"\n> Chunks: {', '.join(map(str, citation.chunk_indexes))}")
        if citation.excerpts:
            for excerpt in citation.excerpts:
                runs = re.findall(r"`+", excerpt)
                fence = "`" * max(3, 1 + max(map(len, runs), default=0))
                parts.append(f"{fence}text\n{excerpt}\n{fence}")
        else:
            parts.append("> No excerpt snapshot was stored for this reference.")
    return "\n\n".join(parts)
