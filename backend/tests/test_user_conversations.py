from conversation import get_user_conversations


def test_user_conversations_includes_participating_conversation(
    db_session, test_users, test_conversation
):
    alice, _ = test_users

    conversations = get_user_conversations(
        db_session,
        user_id=alice.id,
    )

    conversation_ids = [row[0] for row in conversations]

    assert test_conversation.id in conversation_ids


def test_user_without_conversations_returns_empty_list(
    db_session
):
    from auth import register_user

    user = register_user(
        db_session,
        "lonely_user",
        "lonely_user@example.com",
        "Lonely@Test123",
    )

    conversations = get_user_conversations(
        db_session,
        user_id=user.id,
    )

    assert conversations == []