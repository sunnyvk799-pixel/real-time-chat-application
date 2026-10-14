from message import get_messages, send_message


def test_user_messages_returns_messages_for_conversation(
    db_session, test_users, test_conversation
):
    alice, bob = test_users

    send_message(
        db_session,
        conversation_id=test_conversation.id,
        sender_id=alice.id,
        content="Message from Alice",
    )

    send_message(
        db_session,
        conversation_id=test_conversation.id,
        sender_id=bob.id,
        content="Message from Bob",
    )

    messages = get_messages(
        db_session,
        conversation_id=test_conversation.id,
    )

    assert len(messages) == 2
    assert [message.content for message in messages] == [
        "Message from Alice",
        "Message from Bob",
    ]