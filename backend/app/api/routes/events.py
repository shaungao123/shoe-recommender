"""POST /events — persist anonymous product telemetry."""

from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.db.repositories.events import create_event
from app.db.session import get_db
from app.schemas.events import ProductEventRequest, ProductEventResponse

router = APIRouter(prefix="/events", tags=["events"])


@router.post("", response_model=ProductEventResponse, status_code=201)
def post_event(
    body: ProductEventRequest, db: Annotated[Session, Depends(get_db)]
) -> ProductEventResponse:
    row = create_event(db, body)
    return ProductEventResponse(id=row.id)
