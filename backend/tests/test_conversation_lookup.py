from conversation import find_conversation, get_or_create_conversation


def test_find_existing_conversation(db_session, test_users, test_conversation):
    alice, bob = test_users

    conversation = find_conversation(
        db_session,
        user1_id=alice.id,
        user2_id=bob.id,
    )

    assert conversation is not None
    assert conversation.id == test_conversation.id


def test_find_nonexistent_conversation_returns_none(
    db_session, test_users
):
    alice, _ = test_users

    conversation = find_conversation(
        db_session,
        user1_id=alice.id,
        user2_id=999999,
    )

    assert conversation is None


def test_get_or_create_returns_existing_conversation(
    db_session, test_users, test_conversation
):
    alice, bob = test_users

    conversation = get_or_create_conversation(
        db_session,
        user1_id=alice.id,
        user2_id=bob.id,
    )

    assert conversation.id == test_conversation.id