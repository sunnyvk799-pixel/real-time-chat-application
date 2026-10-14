from auth import register_user, authenticate_user


def test_register_user_successfully(db_session):
    user = register_user(
        db_session,
        "register_alice",
        "register_alice@example.com",
        "Alice@Test123",
    )

    assert user.username == "register_alice"
    assert user.email == "register_alice@example.com"
    assert user.password_hash != "Alice@Test123"


def test_register_duplicate_username_returns_error(db_session):
    register_user(
        db_session,
        "duplicate_alice",
        "first_alice@example.com",
        "Alice@Test123",
    )

    result = register_user(
        db_session,
        "duplicate_alice",
        "second_alice@example.com",
        "Alice@Test123",
    )

    assert result == "username_exists"


def test_register_duplicate_email_returns_error(db_session):
    register_user(
        db_session,
        "first_user",
        "shared@example.com",
        "Alice@Test123",
    )

    result = register_user(
        db_session,
        "second_user",
        "shared@example.com",
        "Alice@Test123",
    )

    assert result == "email_exists"