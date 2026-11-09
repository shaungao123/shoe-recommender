"""Anonymous product instrumentation contract."""

from typing import Literal

from pydantic import BaseModel, Field, model_validator

EventName = Literal[
    "quiz_started", "quiz_submitted", "recommendations_shown", "recommendations_empty",
    "catalog_viewed", "catalog_filtered", "shoe_detail_viewed", "buy_link_clicked",
    "buy_link_unavailable", "feedback_submitted", "api_recoverable_failure", "api_failure",
    "recommendation_viewed", "buy_link_intent", "recommendation_error",
]


class ProductEventRequest(BaseModel):
    session_id: str = Field(min_length=8, max_length=128)
    event_name: EventName
    properties: dict[str, object] = Field(default_factory=dict)

    @model_validator(mode="before")
    @classmethod
    def accept_frontend_event_names(cls, value: object) -> object:
        if not isinstance(value, dict):
            return value
        normalized = dict(value)
        if "event_name" not in normalized and "name" in normalized:
            normalized["event_name"] = normalized["name"]
        return normalized


class ProductEventResponse(BaseModel):
    id: int
