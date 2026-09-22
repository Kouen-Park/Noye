"""Tests for citation mapping.

The final integration test is the one that matters most: it runs the whole
Phase 1 pipeline on a PDF written during the test — extract, chunk, embed,
index, search, answer, cite — and checks that the citation points at the page
the fact was actually written on.
"""

from __future__ import annotations

import httpx
import pytest

from app.config import get_settings
from app.services.citations import Citation, build_citations, format_citations
from app.services.retrieval import SearchResult


def result(
    page: int, *, file_id: str = "file-1", chunk_index: int = 0, score: float = 0.9
) -> SearchResult:
    return SearchResult(
        content=f"text from page {page}",
        file_id=file_id,
        page_number=page,
        chunk_index=chunk_index,
        score=score,
    )


def test_one_chunk_becomes_one_citation() -> None:
    citations = build_citations([result(34)])

    assert citations == [
        Citation(
            file_id="file-1",
            page_number=34,
            chunk_indexes=(0,),
            best_score=0.9,
            file_name=None,
        )
    ]


def test_chunks_from_the_same_page_collapse() -> None:
    citations = build_citations(
        [
            result(34, chunk_index=4, score=0.9),
            result(34, chunk_index=5, score=0.7),
            result(34, chunk_index=6, score=0.5),
        ]
    )

    assert len(citations) == 1
    assert citations[0].chunk_indexes == (4, 5, 6)
    # The group keeps its strongest score, not its last or its average.
    assert citations[0].best_score == 0.9


def test_different_pages_stay_separate() -> None:
    citations = build_citations([result(34), result(41)])

    assert {citation.page_number for citation in citations} == {34, 41}


def test_same_page_number_in_different_files_stays_separate() -> None:
    citations = build_citations(
        [result(34, file_id="algorithms"), result(34, file_id="lecture")]
    )

    assert len(citations) == 2
    assert {citation.file_id for citation in citations} == {"algorithms", "lecture"}


def test_citations_are_ordered_by_best_score() -> None:
    citations = build_citations(
        [result(10, score=0.4), result(20, score=0.95), result(30, score=0.6)]
    )

    assert [citation.page_number for citation in citations] == [20, 30, 10]


def test_ordering_is_deterministic_on_ties() -> None:
    first = build_citations(
        [result(7, file_id="b", score=0.5), result(3, file_id="a", score=0.5)]
    )
    second = build_citations(
        [result(3, file_id="a", score=0.5), result(7, file_id="b", score=0.5)]
    )

    assert first == second
    assert [citation.file_id for citation in first] == ["a", "b"]


def test_no_results_produce_no_citations() -> None:
    assert build_citations([]) == []


def test_file_names_are_applied_when_known() -> None:
    citations = build_citations(
        [result(34, file_id="abc")], file_names={"abc": "Algorithms.pdf"}
    )

    assert citations[0].file_name == "Algorithms.pdf"
    assert citations[0].label == "Algorithms.pdf — page 34"


def test_unknown_file_id_falls_back_to_the_id() -> None:
    citations = build_citations([result(34, file_id="abc")], file_names={"other": "X.pdf"})

    assert citations[0].file_name is None
    assert citations[0].label == "abc — page 34"


def test_format_citations_lists_every_source() -> None:
    citations = build_citations(
        [result(34, file_id="a", score=0.9), result(12, file_id="b", score=0.8)],
        file_names={"a": "Algorithms.pdf", "b": "Lecture-07.pdf"},
    )

    rendered = format_citations(citations)

    assert rendered == (
        "Sources:\nAlgorithms.pdf — page 34\nLecture-07.pdf — page 12"
    )


def test_format_citations_is_empty_without_citations() -> None:
    # An ungrounded answer must not display a bare "Sources:" heading.
    assert format_citations([]) == ""


# --- pageless sources --------------------------------------------------------


def pageless(file_id: str = "notes", chunk_index: int = 0, score: float = 0.9) -> SearchResult:
    return SearchResult(
        content="text from a markdown file",
        file_id=file_id,
        page_number=None,
        chunk_index=chunk_index,
        score=score,
    )


def test_pageless_citation_names_the_file_only() -> None:
    citations = build_citations([pageless()], file_names={"notes": "study-notes.md"})

    assert citations[0].page_number is None
    # Inventing "page 1" here would point at a location the user cannot check.
    assert citations[0].label == "study-notes.md"


def test_pageless_citation_falls_back_to_the_id() -> None:
    assert build_citations([pageless()])[0].label == "notes"


def test_pageless_chunks_from_one_file_collapse_into_one_citation() -> None:
    citations = build_citations(
        [pageless(chunk_index=0, score=0.9), pageless(chunk_index=1, score=0.6)]
    )

    assert len(citations) == 1
    assert citations[0].chunk_indexes == (0, 1)
    assert citations[0].best_score == 0.9


def test_format_citations_mixes_paged_and_pageless_sources() -> None:
    citations = build_citations(
        [result(34, file_id="algo", score=0.95), pageless(file_id="notes", score=0.8)],
        file_names={"algo": "Algorithms.pdf", "notes": "study-notes.md"},
    )

    assert format_citations(citations) == (
        "Sources:\nAlgorithms.pdf — page 34\nstudy-notes.md"
    )


def test_mixed_sources_sort_without_comparing_none_to_a_number() -> None:
    # Equal scores force the tiebreakers to run, where None vs int would raise.
    citations = build_citations(
        [
            pageless(file_id="notes", score=0.5),
            result(3, file_id="algo", score=0.5),
            result(1, file_id="algo", score=0.5),
        ]
    )

    assert [c.label for c in citations] == ["algo — page 1", "algo — page 3", "notes"]


# --- Integration: the whole Phase 1 pipeline ---------------------------------


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

PIPELINE_FILE = "integration-pipeline-file"


@requires_services
def test_full_pipeline_cites_the_page_the_fact_was_written_on(tmp_path) -> None:
    """Phase 1's exit condition, end to end, from a PDF on disk."""
    import pymupdf
    from qdrant_client import QdrantClient

    from app.services.chunking import chunk_pages
    from app.services.embeddings import embed_chunks
    from app.services.extraction import extract_pdf
    from app.services.generation import answer_question
    from app.services.indexing import delete_file_chunks, index_chunks

    # A three-page PDF where the answer lives only on page 2.
    pdf_path = tmp_path / "graphs.pdf"
    document = pymupdf.open()
    for text in (
        "Chapter one introduces graphs, vertices and edges in general terms.",
        "Dijkstra's algorithm always selects the unvisited vertex whose distance "
        "estimate is smallest, drawing it from a priority queue.",
        "Chapter three covers unrelated material about sorting networks.",
    ):
        page = document.new_page()
        page.insert_textbox(pymupdf.Rect(60, 60, 540, 300), text, fontsize=11)
    document.save(pdf_path)
    document.close()

    client = QdrantClient(url=get_settings().qdrant_url)
    try:
        pages = extract_pdf(pdf_path)
        chunks = chunk_pages(pages, file_id=PIPELINE_FILE)
        index_chunks(chunks, embed_chunks(chunks), client=client)

        answer = answer_question(
            "How does Dijkstra choose the next vertex?",
            file_ids=[PIPELINE_FILE],
            qdrant_client=client,
        )
        citations = build_citations(
            answer.sources, file_names={PIPELINE_FILE: "graphs.pdf"}
        )

        assert answer.is_grounded
        assert citations, "a grounded answer must carry at least one citation"
        # The fact was written on page 2 and nowhere else.
        assert citations[0].page_number == 2
        assert citations[0].label == "graphs.pdf — page 2"
        assert "graphs.pdf — page 2" in format_citations(citations)
    finally:
        delete_file_chunks(PIPELINE_FILE, client=client)
        client.close()
