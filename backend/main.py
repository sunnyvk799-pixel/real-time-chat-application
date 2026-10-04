from fastapi import FastAPI, WebSocket, WebSocketDisconnect

app = FastAPI()

connected_users = {}


@app.get("/")
def root():
    return {"message": "Chat server is running"}


@app.websocket("/ws/{username}")
async def websocket_endpoint(websocket: WebSocket, username: str):
    await websocket.accept()
    if username in connected_users:
        await websocket.close(code=1008)
        return
    connected_users[username] = websocket

    try:
        while True:
            message = await websocket.receive_text()

            for user, connection in connected_users.items():
                if user != username:
                    await connection.send_text(
                        f"{username}: {message}"
                    )

    except WebSocketDisconnect:
        connected_users.pop(username, None)