"""Feedback persistence queries."""

from sqlalchemy.orm import Session

from app.schemas.feedback import FeedbackRequest
from shared.db.models import Feedback


def create_feedback(session: Session, payload: FeedbackRequest) -> Feedback:
    row = Feedback(
        session_id=payload.session_id,
        shoe_id=payload.shoe_id,
        vote=payload.vote,
        reasons=payload.reasons,
        comment=payload.comment,
        request_context=payload.request_context,
    )
    session.add(row)
    session.commit()
    session.refresh(row)
    return row
