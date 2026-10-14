from auth import authenticate_user, register_user


def test_login_with_correct_credentials(db_session):
    register_user(
        db_session,
        "login_alice",
        "login_alice@example.com",
        "Alice@Test123",
    )

    user = authenticate_user(
        db_session,
        "login_alice",
        "Alice@Test123",
    )

    assert user is not None
    assert user.username == "login_alice"


def test_login_with_wrong_password_fails(db_session):
    register_user(
        db_session,
        "login_bob",
        "login_bob@example.com",
        "Bob@Test123",
    )

    user = authenticate_user(
        db_session,
        "login_bob",
        "WrongPassword",
    )

    assert user is None


def test_login_with_unknown_username_fails(db_session):
    user = authenticate_user(
        db_session,
        "unknown_test_user",
        "SomePassword123",
    )

    assert user is None