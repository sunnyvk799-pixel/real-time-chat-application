from auth import hash_password, verify_password


def test_hash_password_returns_hash():
    password = "Alice@123"

    password_hash = hash_password(password)

    assert password_hash != password
    assert password_hash


def test_correct_password_is_verified():
    password = "Alice@123"

    password_hash = hash_password(password)

    assert verify_password(password, password_hash) is True


def test_wrong_password_is_rejected():
    password_hash = hash_password("Alice@123")

    assert verify_password("WrongPassword", password_hash) is False