from message import send_message, get_messages


def test_send_message_persists_message(
    db_session, test_users, test_conversation
):
    alice, _ = test_users

    message = send_message(
        db_session,
        conversation_id=test_conversation.id,
        sender_id=alice.id,
        content="Hello Bob!",
    )

    assert message.id is not None
    assert message.conversation_id == test_conversation.id
    assert message.sender_id == alice.id
    assert message.content == "Hello Bob!"

    retrieved = get_messages(
        db_session,
        conversation_id=test_conversation.id,
    )

    assert any(item.id == message.id for item in retrieved)