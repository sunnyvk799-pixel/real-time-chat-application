import os

import pytest
from dotenv import load_dotenv
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.engine import make_url

from database import Base
import models  # Register all ORM models with Base.metadata


load_dotenv(override=True)

test_database_url = os.getenv("TEST_DATABASE_URL")

if not test_database_url:
    raise RuntimeError("TEST_DATABASE_URL is not configured")

test_url = make_url(test_database_url)

if test_url.database != "chat_app_test":
    raise RuntimeError(
        "Tests must use the dedicated chat_app_test database"
    )

development_url = os.getenv("DATABASE_URL")

if development_url:
    development_url_parsed = make_url(development_url)

    same_server = (
        test_url.host == development_url_parsed.host
        and test_url.port == development_url_parsed.port
    )

    same_database = (
        test_url.database == development_url_parsed.database
    )

    if same_server and same_database:
        raise RuntimeError(
            "Test database must be separate from the development database"
        )

test_engine = create_engine(test_database_url)

TestSessionLocal = sessionmaker(
    bind=test_engine,
    autocommit=False,
    autoflush=False,
)


@pytest.fixture(scope="session", autouse=True)
def create_test_schema():
    from database import (
        SessionLocal,
        configure_session_factory,
    )

    original_engine = SessionLocal.kw["bind"]

    configure_session_factory(test_engine)

    try:
        Base.metadata.create_all(bind=test_engine)
        yield
    finally:
        configure_session_factory(original_engine)
        test_engine.dispose()


@pytest.fixture
def db_session():
    connection = test_engine.connect()
    outer_transaction = connection.begin()

    session = TestSessionLocal(
        bind=connection,
        join_transaction_mode="create_savepoint",
    )

    try:
        yield session
    finally:
        session.close()
        if outer_transaction.is_active:
            outer_transaction.rollback()
        connection.close()
from auth import hash_password
from models import User, Conversation, ConversationParticipant


@pytest.fixture
def test_users(db_session):
    alice = User(
        username="test_alice",
        email="test_alice@example.com",
        password_hash=hash_password("Alice@Test123"),
    )
    bob = User(
        username="test_bob",
        email="test_bob@example.com",
        password_hash=hash_password("Bob@Test123"),
    )

    db_session.add_all([alice, bob])
    db_session.flush()

    return alice, bob


@pytest.fixture
def test_conversation(db_session, test_users):
    alice, bob = test_users

    conversation = Conversation()
    db_session.add(conversation)
    db_session.flush()

    db_session.add_all([
        ConversationParticipant(
            conversation_id=conversation.id,
            user_id=alice.id,
        ),
        ConversationParticipant(
            conversation_id=conversation.id,
            user_id=bob.id,
        ),
    ])
    db_session.flush()

    return conversation