
import asyncio
import json
from collections.abc import Awaitable, Callable
from typing import Any

from redis_client import redis_client


CHANNEL_NAME = "chat_messages"

EventHandler = Callable[[dict[str, Any]], Awaitable[None]]


async def subscribe_to_chat_messages(
    handle_event: EventHandler,
) -> None:
    pubsub = redis_client.pubsub()

    await asyncio.to_thread(pubsub.subscribe, CHANNEL_NAME)
    print(f"Subscribed to Redis channel: {CHANNEL_NAME}")

    try:
        while True:
            message = await asyncio.to_thread(
                pubsub.get_message,
                ignore_subscribe_messages=True,
                timeout=1.0,
            )

            if message and message["type"] == "message":
                try:
                    event = json.loads(message["data"])
                    await handle_event(event)
                except (json.JSONDecodeError, TypeError, ValueError) as error:
                    print(f"Invalid Redis event: {error}")
                except Exception as error:
                    print(f"Error handling Redis event: {error}")

            await asyncio.sleep(0.01)

    finally:
        await asyncio.to_thread(pubsub.unsubscribe, CHANNEL_NAME)
        await asyncio.to_thread(pubsub.close)


def publish_chat_message(event: dict[str, Any]) -> None:
    redis_client.publish(CHANNEL_NAME, json.dumps(event))
