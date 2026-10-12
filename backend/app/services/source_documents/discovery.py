"""Scoped text search hints over frozen extraction, separate from consumption coverage."""

from app.services.wiki.relations import terms


def search_hints(connection, topic, manifest, checkpoint=lambda: None):
    wanted, hints = terms(topic), {}
    for item in manifest:
        checkpoint()
        if item["root_id"]:
            rows = connection.execute(
                "SELECT content FROM source_passages WHERE file_id=? AND version=?",
                (item["source_id"], item["version"]),
            )
        else:
            rows = connection.execute(
                "SELECT c.content FROM chunks c JOIN files f ON f.id=c.file_id "
                "WHERE c.file_id=? AND f.content_hash=?",
                (item["source_id"], item["version"]),
            )
        found, matches = set(), 0
        for row in rows:
            overlap = wanted & terms(row[0])
            if overlap:
                matches += 1
                found.update(overlap)
        hints[item["source_id"]] = {"matching_passages": matches, "matched_terms": sorted(found)}
    return hints
