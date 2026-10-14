import json
import time
import uuid
import pytest
from fastapi.testclient import TestClient

from auth import hash_password
from database import SessionLocal
from main import app
from models import (
    User,
    Message,
    Conversation,
    ConversationParticipant,
)



def test_websocket_rejects_missing_token():
    with TestClient(app) as client:
        with pytest.raises(Exception):
            with client.websocket_connect("/ws"):
                pass


def test_websocket_rejects_invalid_token():
    with TestClient(app) as client:
        with pytest.raises(Exception):
            with client.websocket_connect("/ws?token=invalid-token"):
                pass


def test_websocket_delivers_message_between_users():
    suffix = uuid.uuid4().hex[:8]
    alice_name = f"ws_alice_{suffix}"
    bob_name = f"ws_bob_{suffix}"
    password = "Alice@Test123"
    bob_password = "Bob@Test123"

    db = SessionLocal()
    alice_id = None
    bob_id = None

    try:
        alice = User(
            username=alice_name,
            email=f"{alice_name}@example.com",
            password_hash=hash_password(password),
        )
        bob = User(
            username=bob_name,
            email=f"{bob_name}@example.com",
            password_hash=hash_password(bob_password),
        )

        db.add_all([alice, bob])
        db.commit()

        alice_id = alice.id
        bob_id = bob.id

        with TestClient(app) as client:
            alice_login = client.post(
                "/login",
                json={
                    "username": alice_name,
                    "password": password,
                },
            )
            bob_login = client.post(
                "/login",
                json={
                    "username": bob_name,
                    "password": bob_password,
                },
            )

            assert alice_login.status_code == 200
            assert bob_login.status_code == 200

            alice_token = alice_login.json()["access_token"]
            bob_token = bob_login.json()["access_token"]

            with (
                client.websocket_connect(
                    f"/ws?token={alice_token}"
                ) as alice_ws,
                client.websocket_connect(
                    f"/ws?token={bob_token}"
                ) as bob_ws,
            ):
                # Allow the connections and Redis subscriptions to initialize.
                time.sleep(0.5)

                content = f"WebSocket test message {suffix}"

                alice_ws.send_text(
                    json.dumps({
                        "recipient": bob_name,
                        "content": content,
                    })
                )

                # Wait for the sender's echo, ignoring unrelated events.
                sender_message = None
                deadline = time.monotonic() + 5

                while time.monotonic() < deadline:
                    event = json.loads(alice_ws.receive_text())

                    if (
                        event.get("content") == content
                        and event.get("sender") == alice_name
                    ):
                        sender_message = event
                        break

                assert sender_message is not None, (
                    "Sender did not receive the message echo"
                )
                assert sender_message["recipient"] == bob_name

                # Wait for the recipient's message.
                recipient_message = None
                deadline = time.monotonic() + 5

                while time.monotonic() < deadline:
                    event = json.loads(bob_ws.receive_text())

                    if (
                        event.get("content") == content
                        and event.get("sender") == alice_name
                    ):
                        recipient_message = event
                        break

                assert recipient_message is not None, (
                    "Recipient did not receive the message"
                )
                assert recipient_message["recipient"] == bob_name

        # Verify that the message was persisted in the test database.
        saved_message = (
            db.query(Message)
            .filter(Message.content == content)
            .first()
        )

        assert saved_message is not None
        assert saved_message.sender_id == alice_id

    finally:
        try:
            if alice_id is not None and bob_id is not None:
                user_ids = [alice_id, bob_id]

                conversation_ids = [
                    row[0]
                    for row in db.query(
                        ConversationParticipant.conversation_id
                    )
                    .filter(
                        ConversationParticipant.user_id.in_(user_ids)
                    )
                    .distinct()
                    .all()
                ]

                if conversation_ids:
                    # Clear foreign-key references before deleting messages.
                    db.query(ConversationParticipant).filter(
                        ConversationParticipant.conversation_id.in_(
                            conversation_ids
                        )
                    ).update(
                        {
                            ConversationParticipant.last_delivered_message_id: None,
                            ConversationParticipant.last_read_message_id: None,
                        },
                        synchronize_session=False,
                    )
                    db.flush()

                    db.query(Message).filter(
                        Message.conversation_id.in_(conversation_ids)
                    ).delete(synchronize_session=False)

                    db.query(ConversationParticipant).filter(
                        ConversationParticipant.conversation_id.in_(
                            conversation_ids
                        )
                    ).delete(synchronize_session=False)

                    db.query(Conversation).filter(
                        Conversation.id.in_(conversation_ids)
                    ).delete(synchronize_session=False)

                db.query(User).filter(
                    User.id.in_(user_ids)
                ).delete(synchronize_session=False)

                db.commit()
        finally:
            db.close()
from main import connected_users
from redis_client import redis_client


def test_websocket_disconnect_cleans_up_presence():
    suffix = uuid.uuid4().hex[:8]
    username = f"ws_disconnect_{suffix}"
    password = "Disconnect@Test123"

    db = SessionLocal()

    try:
        user = User(
            username=username,
            email=f"{username}@example.com",
            password_hash=hash_password(password),
        )
        db.add(user)
        db.commit()
        user_id = user.id

        with TestClient(app) as client:
            login = client.post(
                "/login",
                json={
                    "username": username,
                    "password": password,
                },
            )
            assert login.status_code == 200

            token = login.json()["access_token"]

            with client.websocket_connect(f"/ws?token={token}"):
                assert username in connected_users
                assert redis_client.get(
                    f"presence:user:{user_id}"
                ) == "online"

            # Exiting the context closes the WebSocket.
            # Give the endpoint a chance to process the disconnect.
            deadline = time.monotonic() + 3

            while time.monotonic() < deadline:
                if username not in connected_users:
                    break
                time.sleep(0.05)

            assert username not in connected_users
            assert redis_client.get(
                f"presence:user:{user_id}"
            ) == "offline"
            assert redis_client.get(
                f"last_seen:user:{user_id}"
            ) is not None

    finally:
        try:
            db.query(User).filter(
                User.id == user_id
            ).delete(synchronize_session=False)
            db.commit()
        finally:
            db.close()
def test_websocket_malformed_json_cleans_up_connection():
    suffix = uuid.uuid4().hex[:8]
    username = f"ws_bad_json_{suffix}"
    password = "Malformed@Test123"
    user_id = None

    db = SessionLocal()

    try:
        user = User(
            username=username,
            email=f"{username}@example.com",
            password_hash=hash_password(password),
        )
        db.add(user)
        db.commit()
        user_id = user.id

        with TestClient(app) as client:
            login = client.post(
                "/login",
                json={
                    "username": username,
                    "password": password,
                },
            )
            assert login.status_code == 200
            token = login.json()["access_token"]

            with client.websocket_connect(
                f"/ws?token={token}"
            ) as websocket:
                assert username in connected_users

                websocket.send_text("{")

                deadline = time.monotonic() + 3
                while time.monotonic() < deadline:
                    if username not in connected_users:
                        break
                    time.sleep(0.05)

                assert username not in connected_users
                assert redis_client.get(
                    f"presence:user:{user_id}"
                ) == "offline"

    finally:
        try:
            if user_id is not None:
                db.query(User).filter(
                    User.id == user_id
                ).delete(synchronize_session=False)
                db.commit()
        finally:
            db.close()

def test_offline_message_is_delivered_after_reconnect():
    suffix = uuid.uuid4().hex[:8]
    alice_name = f"ws_sender_{suffix}"
    bob_name = f"ws_offline_{suffix}"
    password = "Reconnect@Test123"
    user_ids = []

    db = SessionLocal()

    try:
        alice = User(
            username=alice_name,
            email=f"{alice_name}@example.com",
            password_hash=hash_password(password),
        )
        bob = User(
            username=bob_name,
            email=f"{bob_name}@example.com",
            password_hash=hash_password(password),
        )
        db.add_all([alice, bob])
        db.commit()

        alice_id = alice.id
        bob_id = bob.id
        user_ids.extend([alice_id, bob_id])

        with TestClient(app) as client:
            # Log in both users.
            alice_login = client.post(
                "/login",
                json={
                    "username": alice_name,
                    "password": password,
                },
            )
            bob_login = client.post(
                "/login",
                json={
                    "username": bob_name,
                    "password": password,
                },
            )

            assert alice_login.status_code == 200
            assert bob_login.status_code == 200

            alice_token = alice_login.json()["access_token"]
            bob_token = bob_login.json()["access_token"]

            # Connect Bob briefly, then disconnect him.
            with client.websocket_connect(
                f"/ws?token={bob_token}"
            ):
                assert bob_name in connected_users

            deadline = time.monotonic() + 3
            while (
                bob_name in connected_users
                and time.monotonic() < deadline
            ):
                time.sleep(0.05)

            assert bob_name not in connected_users

            # Alice sends a message while Bob is offline.
            with client.websocket_connect(
                f"/ws?token={alice_token}"
            ) as alice_ws:
                content = f"Offline delivery {suffix}"
                alice_ws.send_text(
                    json.dumps({
                        "recipient": bob_name,
                        "content": content,
                    })
                )

                deadline = time.monotonic() + 5
                while time.monotonic() < deadline:
                    event = json.loads(alice_ws.receive_text())
                    if event.get("content") == content:
                        break
                else:
                    raise AssertionError(
                        "Sender did not receive message echo"
                    )

            # Bob reconnects and should receive the pending message.
            with client.websocket_connect(
                f"/ws?token={bob_token}"
            ) as bob_ws:
                deadline = time.monotonic() + 5
                while time.monotonic() < deadline:
                    event = json.loads(bob_ws.receive_text())
                    if (
                        event.get("content") == content
                        and event.get("sender") == alice_name
                        and event.get("conversation_id") is not None
                    ):
                        break
                else:
                    raise AssertionError(
                        "Offline message was not delivered after reconnect"
                    )

                print("RECONNECT EVENT:", event)
                assert event["sender"] == alice_name
                assert event["content"] == content
    finally:
        try:
            if len(user_ids) == 2:
                conversation_ids = [
                    row[0]
                    for row in db.query(
                        ConversationParticipant.conversation_id
                    )
                    .filter(
                        ConversationParticipant.user_id.in_(user_ids)
                    )
                    .distinct()
                    .all()
                ]

                if conversation_ids:
                    db.query(ConversationParticipant).filter(
                        ConversationParticipant.conversation_id.in_(
                            conversation_ids
                        )
                    ).update(
                        {
                            ConversationParticipant.last_delivered_message_id: None,
                            ConversationParticipant.last_read_message_id: None,
                        },
                        synchronize_session=False,
                    )
                    db.flush()

                    db.query(Message).filter(
                        Message.conversation_id.in_(conversation_ids)
                    ).delete(synchronize_session=False)

                    db.query(ConversationParticipant).filter(
                        ConversationParticipant.conversation_id.in_(
                            conversation_ids
                        )
                    ).delete(synchronize_session=False)

                    db.query(Conversation).filter(
                        Conversation.id.in_(conversation_ids)
                    ).delete(synchronize_session=False)

                db.query(User).filter(
                    User.id.in_(user_ids)
                ).delete(synchronize_session=False)
                db.commit()
        finally:
            db.close()
