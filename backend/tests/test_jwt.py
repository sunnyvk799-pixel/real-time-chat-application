from auth import create_access_token, verify_access_token


def test_create_access_token_returns_token():
    token = create_access_token(user_id=1)

    assert isinstance(token, str)
    assert len(token) > 0


def test_valid_access_token_returns_user_id():
    token = create_access_token(user_id=1)

    user_id = verify_access_token(token)

    assert user_id == 1


def test_different_user_ids_are_preserved():
    token = create_access_token(user_id=42)

    assert verify_access_token(token) == 42