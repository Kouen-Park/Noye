"""Source-driven requests: conversation context is intent, never evidence."""

from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field

from app.models.wiki import WikiScope


class Strict(BaseModel):
    model_config = ConfigDict(extra="forbid")


class GenerateRequest(Strict):
    request_id: str = Field(min_length=1, max_length=100)
    instruction: str = Field(min_length=1, max_length=4000)
    scope: WikiScope
    conversation_id: str | None = None
    intent_context: list[str] = Field(default_factory=list, max_length=6)
    inventory_mode: Literal["auto", "collection", "relevant"] = "auto"


class Intent(Strict):
    purpose: str = Field(min_length=1, max_length=600)
    topic: str = Field(min_length=1, max_length=300)
    document_type: str = Field(min_length=1, max_length=100)
    language: str = Field(min_length=1, max_length=80)
    inventory_mode: Literal["collection", "relevant"]
    collection_query: str = Field(max_length=300)
    clarification: str | None


class Selection(Strict):
    source_ids: list[str]


class Heading(Strict):
    id: str = Field(min_length=1, max_length=40)
    title: str = Field(min_length=1, max_length=200)


class Outline(Strict):
    title: str = Field(min_length=1, max_length=200)
    sections: list[Heading] = Field(min_length=1, max_length=8)


class Claim(Strict):
    section_id: str
    evidence_ids: list[str] = Field(
        min_length=1,
        max_length=4,
        description="Select supplied evidence IDs before writing one supported assertion.",
    )
    text: str = Field(
        min_length=1,
        max_length=1500,
        description="One source-grounded assertion in output_language. Preserve the subject, "
        "measured property, units, relationships, conditions and exceptions.",
    )


class Extraction(Strict):
    claims: list[Claim] = Field(max_length=12)
    gaps: list[str] = Field(max_length=8)


class SynthesizedClaim(Strict):
    claim_ids: list[str] = Field(min_length=1, max_length=12)
    text: str = Field(
        min_length=1,
        max_length=1800,
        description="Source-grounded prose in output_language. Combine sources only where "
        "they establish the relationship; keep independent facts independent. Preserve each "
        "subject, measured property, unit, condition and exception.",
    )


class Synthesis(Strict):
    claims: list[SynthesizedClaim] = Field(max_length=12)


class Verification(Strict):
    supported: list[bool]


class SupportAudit(Strict):
    claim_index: int = Field(ge=0, description="Copy the claim_index from the input claim.")
    original_indexes: list[Annotated[int, Field(ge=0)]] = Field(
        max_length=4,
        description="Select all relevant original indexes from this claim's allowed list. "
        "Different assertions may rely on different originals.",
    )
    unestablished: list[Annotated[str, Field(min_length=1, max_length=1800)]] = Field(
        max_length=6,
        description="Exact claim substrings with unsupported assertions or lost conditions. "
        "Empty when fully entailed.",
    )
    supported: bool


class SupportVerification(Strict):
    audits: list[SupportAudit] = Field(max_length=12)


class EditRequest(Strict):
    expected_revision: str
    title: str = Field(min_length=1, max_length=200)
    content: str
