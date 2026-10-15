"""Scoped text search hints over frozen extraction, separate from consumption coverage."""

from app.services.wiki.relations import terms


def search_hints(connection, topic, manifest, checkpoint=lambda: None):
    wanted, hints = terms(topic), {}
    for item in manifest:
        checkpoint()
        if item["root_id"]:
            rows = connection.execute(
                "SELECT content FROM source_passages WHERE file_id=? AND version=? "
                "ORDER BY chunk_index",
                (item["source_id"], item["version"]),
            )
        else:
            rows = connection.execute(
                "SELECT c.content FROM chunks c JOIN files f ON f.id=c.file_id "
                "WHERE c.file_id=? AND f.content_hash=? ORDER BY c.chunk_index",
                (item["source_id"], item["version"]),
            )
        found, matches, preview = set(), 0, ""
        for row in rows:
            if not preview:
                preview = row[0][:360]
            overlap = wanted & terms(row[0])
            if overlap:
                if not matches:
                    preview = row[0][:360]
                matches += 1
                found.update(overlap)
        hints[item["source_id"]] = {
            "matching_passages": matches,
            "matched_terms": sorted(found),
            "preview": preview,
        }
    return hints
