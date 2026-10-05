"""Wiki interpretations, immutable evidence and explicit bounded source scopes."""

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)


class WikiScope(StrictModel):
    mode: Literal["all", "empty", "chosen"] = "all"
    source_ids: list[str] = Field(default_factory=list, max_length=1000)
    root_ids: list[str] = Field(default_factory=list, max_length=100)

    @model_validator(mode="after")
    def coherent(self):
        if self.mode != "chosen" and (self.source_ids or self.root_ids):
            raise ValueError("Only a chosen scope can contain IDs")
        if self.mode == "chosen" and not (self.source_ids or self.root_ids):
            raise ValueError("Use empty for an explicitly empty scope")
        return self


class SourceRef(StrictModel):
    source_id: str
    root_id: str | None
    relative_path: str
    name: str
    source_hash: str
    source_version: str
    availability: str
    indexing_status: str


class Passage(StrictModel):
    id: str
    source: SourceRef
    page_number: int | None = Field(default=None, ge=1)
    passage_index: int = Field(ge=0)
    start: int = Field(ge=0)
    end: int = Field(ge=0)
    text: str


class Claim(StrictModel):
    text: str = Field(min_length=1, max_length=1200)
    evidence_id: str = Field(min_length=1)
    quote: str = Field(min_length=1, max_length=1200)


class Topic(StrictModel):
    title: str = Field(min_length=1, max_length=100)
    kind: Literal["concept", "project"]


class SectionSummary(StrictModel):
    summary: Claim
    key_points: list[Claim] = Field(max_length=6)
    uncertainties: list[str] = Field(max_length=5)
    primary_category: str = Field(min_length=1, max_length=100)
    category_confidence: float = Field(ge=0, le=1)
    tags: list[str] = Field(max_length=8)
    topics: list[Topic] = Field(max_length=3)


RelationType = Literal["shared_subject", "supporting_evidence", "alternative", "contradiction"]


class RelationProposal(StrictModel):
    target_id: str
    kind: RelationType
    reason: str = Field(min_length=1, max_length=800)
    confidence: float = Field(ge=0, le=1)
    origin_evidence_id: str
    target_evidence_id: str


class RelationsOutput(StrictModel):
    relations: list[RelationProposal] = Field(max_length=6)


class EditWiki(StrictModel):
    expected_revision: str
    title: str = Field(min_length=1, max_length=160)
    content: str = Field(max_length=200_000)
    scope: WikiScope = Field(default_factory=WikiScope)


class SaveAnalysis(StrictModel):
    title: str = Field(min_length=1, max_length=160)
    content: str = Field(max_length=200_000)
    wiki_ids: list[str] = Field(min_length=1, max_length=20)
    scope: WikiScope = Field(default_factory=WikiScope)
