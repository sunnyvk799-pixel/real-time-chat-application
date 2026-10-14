import asyncio
import threading

import pytest

from redis_client import redis_client
from redis_pubsub import CHANNEL_NAME, subscribe_to_chat_messages


@pytest.mark.asyncio
async def test_pubsub_delivers_event():
    received_events = []
    event_received = threading.Event()

    async def handle_event(event: dict) -> None:
        received_events.append(event)
        event_received.set()

    async def run_subscriber():
        await subscribe_to_chat_messages(handle_event)

    subscriber_task = asyncio.create_task(run_subscriber())

    try:
        # Allow the subscriber to establish its Redis subscription.
        await asyncio.sleep(0.5)

        event = {
            "type": "test",
            "message": "pytest pubsub event",
        }

        await asyncio.to_thread(
            redis_client.publish,
            CHANNEL_NAME,
            __import__("json").dumps(event),
        )

        received = await asyncio.to_thread(event_received.wait, 3)

        assert received, "Subscriber did not receive the published event"
        assert received_events[0] == event

    finally:
        subscriber_task.cancel()
        try:
            await subscriber_task
        except asyncio.CancelledError:
            pass
@pytest.mark.asyncio
async def test_pubsub_closes_resources_when_cancelled():
    pubsub = redis_client.pubsub()
    original_pubsub = redis_client.pubsub

    # Ensure the subscriber uses this exact Pub/Sub object.
    redis_client.pubsub = lambda: pubsub

    async def handle_event(event: dict) -> None:
        pass

    task = asyncio.create_task(
        subscribe_to_chat_messages(handle_event)
    )

    try:
        # Wait until the subscription is established.
        await asyncio.sleep(0.5)

        task.cancel()

        with pytest.raises(asyncio.CancelledError):
            await task

        # The subscriber's finally block should have closed it.
        assert pubsub.connection is None

    finally:
        redis_client.pubsub = original_pubsub

        if not task.done():
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass
