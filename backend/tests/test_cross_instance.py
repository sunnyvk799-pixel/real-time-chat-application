import asyncio
import json
import time
import urllib.error
import urllib.request
import uuid

import websockets


BASE_URL = "http://127.0.0.1:8081"
WS_URL = "ws://127.0.0.1:8081/ws"


def post_json(path, payload):
    request = urllib.request.Request(
        f"{BASE_URL}{path}",
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )

    try:
        with urllib.request.urlopen(request, timeout=10) as response:
            return response.status, json.loads(response.read())
    except urllib.error.HTTPError as error:
        body = error.read().decode("utf-8", errors="replace")
        raise RuntimeError(
            f"{path} failed: HTTP {error.code}: {body}"
        ) from error


async def receive_matching(websocket, content, timeout=10):
    deadline = time.monotonic() + timeout

    while time.monotonic() < deadline:
        remaining = deadline - time.monotonic()
        raw = await asyncio.wait_for(
            websocket.recv(),
            timeout=remaining,
        )
        event = json.loads(raw)

        if event.get("content") == content:
            return event

    raise AssertionError(
        f"Did not receive message with content: {content}"
    )


async def main():
    suffix = uuid.uuid4().hex[:10]
    alice = f"cross_alice_{suffix}"
    bob = f"cross_bob_{suffix}"
    password = f"CrossTest@{uuid.uuid4().hex[:12]}"
    content = f"Cross-instance test {suffix}"

    # Create unique accounts in the isolated test environment.
    for username in (alice, bob):
        status, result = post_json(
            "/register",
            {
                "username": username,
                "email": f"{username}@example.com",
                "password": password,
            },
        )
        print(f"Registered {username}: HTTP {status}")

    _, alice_login = post_json(
        "/login",
        {"username": alice, "password": password},
    )
    _, bob_login = post_json(
        "/login",
        {"username": bob, "password": password},
    )

    alice_token = alice_login["access_token"]
    bob_token = bob_login["access_token"]

    alice_url = f"{WS_URL}?token={alice_token}"
    bob_url = f"{WS_URL}?token={bob_token}"

    async with websockets.connect(alice_url) as alice_ws:
        async with websockets.connect(bob_url) as bob_ws:
            print("Both WebSocket connections established.")

            # Allow connection setup and subscriptions to settle.
            await asyncio.sleep(0.5)

            await alice_ws.send(json.dumps({
                "recipient": bob,
                "content": content,
            }))

            sender_event = await receive_matching(alice_ws, content)
            recipient_event = await receive_matching(bob_ws, content)

            assert sender_event.get("sender") == alice
            assert sender_event.get("recipient") == bob
            print("RECIPIENT EVENT:", recipient_event)
            assert recipient_event.get("sender") == alice

            print("PASS: sender received the message echo.")
            print("PASS: recipient received the message.")
            print("PASS: message fields match the expected users.")
            print(
                "Now confirm in the Uvicorn terminals that the "
                "two WebSocket connections landed on different "
                "instances (8002 and 8003)."
            )


if __name__ == "__main__":
    asyncio.run(main())
