import asyncio

import pytest

from main import presence_heartbeat


@pytest.mark.asyncio
async def test_presence_heartbeat_stops_when_cancelled():
    user_id = 987654321

    task = asyncio.create_task(
        presence_heartbeat(user_id)
    )

    # Allow the heartbeat coroutine to start.
    await asyncio.sleep(0)

    task.cancel()

    # The function catches CancelledError and exits normally.
    await asyncio.wait_for(task, timeout=1)

    assert task.done()
    assert not task.cancelled()
