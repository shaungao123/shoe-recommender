"""Product-event persistence queries."""

from sqlalchemy.orm import Session

from app.schemas.events import ProductEventRequest
from shared.db.models import ProductEvent


def create_event(session: Session, payload: ProductEventRequest) -> ProductEvent:
    row = ProductEvent(
        session_id=payload.session_id,
        event_name=payload.event_name,
        properties=payload.properties,
    )
    session.add(row)
    session.commit()
    session.refresh(row)
    return row
