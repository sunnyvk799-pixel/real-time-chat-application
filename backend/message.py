from sqlalchemy.orm import Session

from models import Message, ConversationParticipant


def send_message(
    db: Session,
    conversation_id: int,
    sender_id: int,
    content: str
):
    message = Message(
        conversation_id=conversation_id,
        sender_id=sender_id,
        content=content
    )

    db.add(message)
    db.commit()
    db.refresh(message)

    return message
def get_messages(
    db: Session,
    conversation_id: int
):
    return (
        db.query(Message)
        .filter(Message.conversation_id == conversation_id)
        .order_by(Message.id.asc())
        .all()
    )
def get_undelivered_messages(
    db: Session,
    conversation_id: int,
    last_delivered_message_id: int | None
):
    query = (
        db.query(Message)
        .filter(
            Message.conversation_id == conversation_id
        )
    )

    if last_delivered_message_id is not None:
        query = query.filter(
            Message.id > last_delivered_message_id
        )

    return query.order_by(Message.id.asc()).all()