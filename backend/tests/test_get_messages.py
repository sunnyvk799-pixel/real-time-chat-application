from message import send_message, get_messages


def test_get_messages_returns_messages_in_order(
    db_session, test_users, test_conversation
):
    alice, bob = test_users

    first = send_message(
        db_session,
        conversation_id=test_conversation.id,
        sender_id=alice.id,
        content="First test message",
    )

    second = send_message(
        db_session,
        conversation_id=test_conversation.id,
        sender_id=bob.id,
        content="Second test message",
    )

    messages = get_messages(
        db_session,
        conversation_id=test_conversation.id,
    )

    assert [message.id for message in messages] == [
        first.id,
        second.id,
    ]
    assert [message.content for message in messages] == [
        "First test message",
        "Second test message",
    ]


def test_get_messages_for_empty_conversation(
    db_session, test_conversation
):
    messages = get_messages(
        db_session,
        conversation_id=test_conversation.id,
    )

    assert messages == []