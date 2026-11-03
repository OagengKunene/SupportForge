"""Typed boundaries for the HTTP API, model response, and persisted workflow."""

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator


class SupportRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    message: str = Field(min_length=5, max_length=6000)
    customer_name: str = Field(default="Customer", min_length=1, max_length=80)

    @field_validator("message", "customer_name")
    @classmethod
    def not_blank(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("Must contain non-whitespace text")
        return value.strip()


class Source(BaseModel):
    id: str
    title: str
    document: str
    excerpt: str


class Triage(BaseModel):
    category: Literal["billing", "account", "technical", "security", "general"]
    priority: Literal["normal", "high", "urgent"]
    queue: str


class ModelDraft(BaseModel):
    model_config = ConfigDict(extra="forbid")
    answer: str = Field(min_length=1, max_length=8000)
    citation_ids: list[str] = Field(default_factory=list, max_length=10)
    needs_human_review: bool = True


class TraceEvent(BaseModel):
    step: str
    detail: str


class Run(BaseModel):
    id: str
    created_at: str
    mode: str
    request: SupportRequest
    triage: Triage
    answer: str
    sources: list[Source]
    citation_ids: list[str]
    review_reasons: list[str]
    trace: list[TraceEvent]
    status: Literal["pending", "approved", "rejected"] = "pending"
    ticket_id: str | None = None


class ReviewRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    decision: Literal["approve", "reject"]
    reviewer: str = Field(min_length=1, max_length=80)
    note: str = Field(default="", max_length=1000)

    @field_validator("reviewer")
    @classmethod
    def reviewer_not_blank(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("Reviewer is required")
        return value.strip()
