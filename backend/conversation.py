from sqlalchemy.orm import Session

from models import Conversation, ConversationParticipant,User


def create_conversation(
    db: Session,
    user1_id: int,
    user2_id: int
):
    conversation = Conversation()

    db.add(conversation)
    db.flush()

    participant1 = ConversationParticipant(
        conversation_id=conversation.id,
        user_id=user1_id
    )

    participant2 = ConversationParticipant(
        conversation_id=conversation.id,
        user_id=user2_id
    )

    db.add(participant1)
    db.add(participant2)

    db.commit()
    db.refresh(conversation)
    return conversation
def find_conversation(
    db: Session,
    user1_id: int,
    user2_id: int
):
    conversation = (
        db.query(ConversationParticipant.conversation_id)
        .filter(
            ConversationParticipant.user_id == user1_id
        )
        .all()
    )
    conversation_ids = [row[0] for row in conversation]
    matching_conversation = (
        db.query(ConversationParticipant.conversation_id)
        .filter(
            ConversationParticipant.conversation_id.in_(conversation_ids),
            ConversationParticipant.user_id == user2_id
        )
        .first()
    )
    if matching_conversation:
        return db.get(Conversation, matching_conversation[0])

    return None
def get_or_create_conversation(
    db: Session,
    user1_id: int,
    user2_id: int
):
    conversation = find_conversation(
    db,
    user1_id,
    user2_id
    )
    if conversation:
        return conversation
    return create_conversation(
        db,
        user1_id,
        user2_id
    )
def get_user_by_username(db: Session, username: str):
    return db.query(User).filter(User.username == username).first()
def get_user_conversations(
    db: Session,
    user_id: int
):
    return (
        db.query(ConversationParticipant.conversation_id)
        .filter(
            ConversationParticipant.user_id == user_id
        )
        .all()
    )
def get_user_participants(
    db: Session,
    user_id: int
):
    return (
        db.query(ConversationParticipant)
        .filter(
            ConversationParticipant.user_id == user_id
        )
        .all()
    )
def update_last_delivered_message(
    db: Session,
    conversation_id: int,
    user_id: int,
    message_id: int
):
    participant = (
        db.query(ConversationParticipant)
        .filter(
            ConversationParticipant.conversation_id == conversation_id,
            ConversationParticipant.user_id == user_id
        )
        .first()
    )

    if participant is None:
        return None

    participant.last_delivered_message_id = message_id

    db.commit()

    return participant

def update_last_read_message(
    db: Session,
    conversation_id: int,
    user_id: int,
    message_id: int
):
    participant = (
        db.query(ConversationParticipant)
        .filter(
            ConversationParticipant.conversation_id == conversation_id,
            ConversationParticipant.user_id == user_id
        )
        .first()
    )

    if participant is None:
        return None

    # Never move the read checkpoint backwards.
    current_read_id = participant.last_read_message_id

    if current_read_id is not None and message_id <= current_read_id:
        return participant

    participant.last_read_message_id = message_id
    db.commit()

    return participant
