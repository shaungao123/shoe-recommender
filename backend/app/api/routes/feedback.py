"""POST /feedback — store anonymous thumbs and qualitative reasons."""

from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.db.repositories.feedback import create_feedback
from app.db.session import get_db
from app.schemas.feedback import FeedbackRequest, FeedbackResponse

router = APIRouter(prefix="/feedback", tags=["feedback"])


@router.post("", response_model=FeedbackResponse, status_code=201)
def post_feedback(
    body: FeedbackRequest, db: Annotated[Session, Depends(get_db)]
) -> FeedbackResponse:
    row = create_feedback(db, body)
    return FeedbackResponse(id=row.id)
