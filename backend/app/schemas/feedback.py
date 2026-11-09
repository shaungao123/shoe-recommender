"""Typed anonymous feedback contract."""

from typing import Literal

from pydantic import BaseModel, Field, field_validator, model_validator

FeedbackVote = Literal["up", "down"]
FeedbackReason = Literal[
    "not_my_playstyle", "too_expensive", "not_my_style", "fit_or_comfort", "other"
]


class FeedbackRequest(BaseModel):
    session_id: str = Field(min_length=8, max_length=128)
    shoe_id: int = Field(gt=0)
    vote: FeedbackVote
    reasons: list[FeedbackReason] = Field(default_factory=list, max_length=5)
    comment: str | None = Field(default=None, max_length=500)
    request_context: dict[str, object] = Field(default_factory=dict)

    @model_validator(mode="before")
    @classmethod
    def accept_frontend_aliases(cls, value: object) -> object:
        if not isinstance(value, dict):
            return value
        normalized = dict(value)
        if "request_context" not in normalized and "request" in normalized:
            normalized["request_context"] = normalized["request"]
        if "reasons" not in normalized and normalized.get("reason"):
            normalized["reasons"] = [normalized["reason"]]
        return normalized

    @field_validator("reasons")
    @classmethod
    def unique_reasons(cls, reasons: list[FeedbackReason]) -> list[FeedbackReason]:
        return list(dict.fromkeys(reasons))


class FeedbackResponse(BaseModel):
    id: int
