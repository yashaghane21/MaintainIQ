"""Schema for AI triage output and evidence.

`AIAnalysisOutput` is the contract every AI provider must satisfy. Provider
output is parsed with `model_validate`; anything that does not conform
(wrong enum values, missing fields, extra keys) is rejected.
"""

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

Confidence = Literal["low", "medium", "high"]
PriorityLiteral = Literal["low", "medium", "high", "critical"]
EvidenceType = Literal["MANUAL", "OPERATING_EVENT", "SENSOR_RULE", "USER_REPORT"]


class _Strict(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


class PossibleCause(_Strict):
    cause: str = Field(min_length=3, max_length=300)
    reasoning: str = Field(min_length=3, max_length=1500)
    confidence: Confidence
    evidence_ids: list[str] = Field(default_factory=list, max_length=12)


class InspectionStep(_Strict):
    step: str = Field(min_length=3, max_length=400)
    reason: str = Field(min_length=3, max_length=1000)
    evidence_ids: list[str] = Field(default_factory=list, max_length=12)


class WorkOrderDraft(_Strict):
    title: str = Field(min_length=5, max_length=160)
    description: str = Field(min_length=10, max_length=4000)
    checklist: list[str] = Field(min_length=1, max_length=25)


class AIAnalysisOutput(_Strict):
    summary: str = Field(min_length=10, max_length=2000)
    observations: list[str] = Field(default_factory=list, max_length=25)
    possible_causes: list[PossibleCause] = Field(min_length=1, max_length=8)
    follow_up_questions: list[str] = Field(default_factory=list, max_length=12)
    inspection_steps: list[InspectionStep] = Field(min_length=1, max_length=15)
    suggested_priority: PriorityLiteral
    priority_reason: str = Field(min_length=5, max_length=1000)
    work_order: WorkOrderDraft
    limitations: list[str] = Field(default_factory=list, max_length=12)


class Evidence(BaseModel):
    evidence_id: str
    evidence_type: EvidenceType
    source: str
    title: str
    excerpt: str
    document_id: str | None = None
    chunk_id: str | None = None
    page_number: int | None = None
    # Cosine similarity from retrieval. This is a relevance score for the text
    # match only and must never be shown as a diagnostic probability.
    retrieval_score: float | None = None
    metadata: dict = Field(default_factory=dict)
