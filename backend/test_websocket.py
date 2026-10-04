import asyncio
import websockets


async def user(username, message):
    uri = f"ws://127.0.0.1:8000/ws/{username}"

    async with websockets.connect(uri) as websocket:
        await websocket.send(message)

        try:
            response = await asyncio.wait_for(
                websocket.recv(),
                timeout=2
            )
            print(f"{username} received: {response}")
        except asyncio.TimeoutError:
            print(f"{username} received nothing")


async def test():
    await asyncio.gather(
        user("Alice", "Hello Bob!"),
        user("Bob", "Hello Alice!")
    )


asyncio.run(test())