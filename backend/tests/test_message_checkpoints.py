from conversation import (
    update_last_delivered_message,
    update_last_read_message,
)
from message import send_message


def test_update_delivery_checkpoint(
    db_session, test_users, test_conversation
):
    alice, bob = test_users

    message = send_message(
        db_session,
        conversation_id=test_conversation.id,
        sender_id=alice.id,
        content="Delivery checkpoint test",
    )

    participant = update_last_delivered_message(
        db_session,
        conversation_id=test_conversation.id,
        user_id=bob.id,
        message_id=message.id,
    )

    assert participant is not None
    assert participant.last_delivered_message_id == message.id


def test_update_read_checkpoint(
    db_session, test_users, test_conversation
):
    alice, bob = test_users

    message = send_message(
        db_session,
        conversation_id=test_conversation.id,
        sender_id=alice.id,
        content="Read checkpoint test",
    )

    participant = update_last_read_message(
        db_session,
        conversation_id=test_conversation.id,
        user_id=bob.id,
        message_id=message.id,
    )

    assert participant is not None
    assert participant.last_read_message_id == message.id


def test_read_checkpoint_does_not_move_backwards(
    db_session, test_users, test_conversation
):
    alice, bob = test_users

    first = send_message(
        db_session,
        conversation_id=test_conversation.id,
        sender_id=alice.id,
        content="First",
    )
    second = send_message(
        db_session,
        conversation_id=test_conversation.id,
        sender_id=alice.id,
        content="Second",
    )

    update_last_read_message(
        db_session,
        conversation_id=test_conversation.id,
        user_id=bob.id,
        message_id=second.id,
    )

    participant = update_last_read_message(
        db_session,
        conversation_id=test_conversation.id,
        user_id=bob.id,
        message_id=first.id,
    )

    assert participant.last_read_message_id == second.id


def test_checkpoint_rejects_nonparticipant(
    db_session, test_users, test_conversation
):
    from auth import register_user

    outsider = register_user(
        db_session,
        "checkpoint_outsider",
        "checkpoint_outsider@example.com",
        "Outsider@Test123",
    )

    result = update_last_read_message(
        db_session,
        conversation_id=test_conversation.id,
        user_id=outsider.id,
        message_id=1,
    )
    assert result is None