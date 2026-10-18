from fastapi import (
    FastAPI,
    WebSocket,
    WebSocketDisconnect,
    Depends,
    HTTPException
)
from contextlib import asynccontextmanager
from redis_pubsub import subscribe_to_chat_messages
from redis_client import redis_client
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from redis_pubsub import publish_chat_message
from sqlalchemy.orm import Session
import asyncio
import json


from database import SessionLocal, get_db
from models import (
    User,
    ConversationParticipant,
    Message
)

from auth import (
    register_user,
    authenticate_user,
    create_access_token,
    verify_access_token
)

from conversation import (
    get_user_by_username,
    get_user_participants,
    get_or_create_conversation,
    update_last_delivered_message
)

from message import (
    send_message,
    get_undelivered_messages
)

from schemas import (
    RegisterRequest,
    LoginRequest,
    LoginResponse
)


from conversation import (
    get_user_by_username,
    get_user_participants,
    get_or_create_conversation,
    update_last_delivered_message,
    update_last_read_message
)




@asynccontextmanager
async def lifespan(app: FastAPI):
    subscriber_task = asyncio.create_task(
        subscribe_to_chat_messages(handle_redis_event)
    )
    try:
        yield
    finally:
        subscriber_task.cancel()
        try:
            await subscriber_task
        except asyncio.CancelledError:
            pass


app = FastAPI(lifespan=lifespan)


# ==================================================
# CORS
# ==================================================

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ==================================================
# Authentication
# ==================================================

security = HTTPBearer()


def get_current_user_id(
    credentials: HTTPAuthorizationCredentials = Depends(security)
):
    token = credentials.credentials

    user_id = verify_access_token(token)

    if user_id is None:
        raise HTTPException(
            status_code=401,
            detail="Invalid or expired token"
        )

    return user_id


# ==================================================
# Connected users
# ==================================================

connected_users = {}



async def handle_redis_event(event: dict) -> None:
    event_type = event.get("type")

    # Handle delivery/read receipt updates
    if event_type == "message_status":
        sender_username = event.get("sender_username")

        if not sender_username:
            return

        sender_session = connected_users.get(sender_username)

        if sender_session is None:
            return

        status_event = {
            "type": "message_status",
            "message_id": event.get("message_id"),
            "conversation_id": event.get("conversation_id"),
            "status": event.get("status"),
        }

        try:
            await sender_session["websocket"].send_text(
                json.dumps(status_event)
            )
        except (WebSocketDisconnect, RuntimeError) as error:
            print(f"Could not deliver message status: {error}")

        return

    # Handle normal chat messages
    if event_type != "chat_message":
        return

    recipient_username = event.get("recipient")

    if not recipient_username:
        return

    recipient_session = connected_users.get(recipient_username)

    if recipient_session is None:
        return

    websocket = recipient_session["websocket"]

    message_data = {
        key: event[key]
        for key in (
            "sender",
            "recipient",
            "content",
            "message_id",
            "conversation_id",
        )
        if key in event
    }

    try:
        await websocket.send_text(json.dumps(message_data))

        recipient_session["checkpoints"][
            message_data["conversation_id"]
        ] = message_data["message_id"]

    except (WebSocketDisconnect, RuntimeError) as error:
        print(f"Could not deliver Redis message: {error}")

def set_user_online(user_id: int):
    redis_client.set(
        f"presence:user:{user_id}",
        "online",
        ex=30
    )


def set_user_offline(user_id: int):
    redis_client.set(
        f"presence:user:{user_id}",
        "offline"
    )


def set_last_seen(user_id: int):
    from datetime import datetime, timezone

    last_seen = datetime.now(timezone.utc).isoformat()

    redis_client.set(
        f"last_seen:user:{user_id}",
        last_seen
    )

    return last_seen


async def presence_heartbeat(user_id: int):
    try:
        while True:
            await asyncio.sleep(10)

            redis_client.set(
                f"presence:user:{user_id}",
                "online",
                ex=30
            )

    except asyncio.CancelledError:
        pass
async def broadcast_presence(
    username: str,
    status: str,
    last_seen: str | None = None
):
    presence_data = {
        "type": "presence",
        "username": username,
        "status": status
    }

    if last_seen is not None:
        presence_data["last_seen"] = last_seen

    presence_json = json.dumps(presence_data)

    disconnected_users = []

    for connected_username, session in list(connected_users.items()):
        # Don't need to notify the user about their own presence.
        if connected_username == username:
            continue

        websocket = session["websocket"]

        try:
            await websocket.send_text(presence_json)

        except Exception:
            disconnected_users.append(connected_username)

    for disconnected_username in disconnected_users:
        connected_users.pop(
            disconnected_username,
            None
        )



async def notify_message_status(
    sender_username: str,
    message_id: int,
    conversation_id: int,
    status: str
):
    status_event = {
        "type": "message_status",
        "sender_username": sender_username,
        "message_id": message_id,
        "conversation_id": conversation_id,
        "status": status
    }

    await asyncio.to_thread(
        publish_chat_message,
        status_event
    )


# ==================================================
# Root
# ==================================================

@app.get("/")
def root():
    return {
        "message": "Chat server is running"
    }


# ==================================================
# Get all users
# ==================================================

@app.get("/users")
def get_users(
    db: Session = Depends(get_db)
):
    users = db.query(User).all()

    return users


# ==================================================
# Get user by username
# ==================================================

@app.get("/users/{username}")
def get_user(
    username: str,
    db: Session = Depends(get_db)
):
    user = (
        db.query(User)
        .filter(User.username == username)
        .first()
    )

    if user is None:
        raise HTTPException(
            status_code=404,
            detail="User not found"
        )

    return {
        "id": user.id,
        "username": user.username
    }


# ==================================================
# Get user's presence
# ==================================================

@app.get("/users/{username}/presence")
def get_user_presence(
    username: str,
    user_id: int = Depends(get_current_user_id),
    db: Session = Depends(get_db)
):
    user = get_user_by_username(db, username)

    if user is None:
        raise HTTPException(
            status_code=404,
            detail="User not found"
        )

    target_user_id = user.id
    target_username = user.username

    # Check the user's current presence in Redis.
    status = redis_client.get(
        f"presence:user:{target_user_id}"
    )

    response = {
        "username": target_username,
        "status": "online" if status == "online" else "offline"
    }

    # Last seen is relevant when the user is offline.
    if response["status"] == "offline":
        last_seen = redis_client.get(
            f"last_seen:user:{target_user_id}"
        )

        response["last_seen"] = last_seen

    return response

# ==================================================
# Register
# ==================================================

@app.post("/register")
def register(
    request: RegisterRequest,
    db: Session = Depends(get_db)
):
    result = register_user(
        db,
        request.username,
        request.email,
        request.password
    )

    if result == "username_exists":
        raise HTTPException(
            status_code=400,
            detail="Username already exists"
        )

    if result == "email_exists":
        raise HTTPException(
            status_code=400,
            detail="Email already exists"
        )

    return {
        "message": "User registered successfully",
        "username": result.username
    }


# ==================================================
# Login
# ==================================================

@app.post(
    "/login",
    response_model=LoginResponse
)
def login(
    request: LoginRequest,
    db: Session = Depends(get_db)
):
    user = authenticate_user(
        db,
        request.username,
        request.password
    )

    if user is None:
        raise HTTPException(
            status_code=401,
            detail="Invalid username or password"
        )

    access_token = create_access_token(
        user.id
    )

    return {
        "access_token": access_token,
        "token_type": "bearer"
    }


# ==================================================
# Current user
# ==================================================

@app.get("/me")
def get_me(
    user_id: int = Depends(get_current_user_id),
    db: Session = Depends(get_db)
):
    user = db.get(User, user_id)

    if user is None:
        raise HTTPException(
            status_code=401,
            detail="User not found"
        )

    # Extract primitive values before the session closes.
    user_id_value = user.id
    username_value = user.username
    email_value = user.email

    return {
        "id": user_id_value,
        "username": username_value,
        "email": email_value
    }


# ==================================================
# Get conversations
# ==================================================

@app.get("/conversations")
def get_conversations(
    user_id: int = Depends(get_current_user_id),
    db: Session = Depends(get_db)
):
    participants = (
        db.query(ConversationParticipant)
        .filter(
            ConversationParticipant.user_id == user_id
        )
        .all()
    )

    conversations = []

    for participant in participants:

        conversation_id = participant.conversation_id

        other_participant = (
            db.query(ConversationParticipant)
            .filter(
                ConversationParticipant.conversation_id
                == conversation_id,

                ConversationParticipant.user_id
                != user_id
            )
            .first()
        )

        if other_participant is None:
            continue

        other_user = db.get(
            User,
            other_participant.user_id
        )

        if other_user is None:
            continue

        # Extract primitive value while session is open.
        other_username = other_user.username

        conversations.append({
            "conversation_id": conversation_id,
            "username": other_username
        })

    return conversations


# ==================================================
# Get messages for one conversation
# ==================================================


@app.get("/conversations/{conversation_id}/messages")
def get_conversation_messages(
    conversation_id: int,
    db: Session = Depends(get_db),
    current_user_id: int = Depends(get_current_user_id),
):
    # 1. Verify that the current user belongs to this conversation.
    current_participant = db.query(ConversationParticipant).filter(
        ConversationParticipant.conversation_id == conversation_id,
        ConversationParticipant.user_id == current_user_id,
    ).first()

    if current_participant is None:
        raise HTTPException(
            status_code=403,
            detail="You are not a participant in this conversation",
        )

    # 2. Find the other participant.
    other_participant = db.query(ConversationParticipant).filter(
        ConversationParticipant.conversation_id == conversation_id,
        ConversationParticipant.user_id != current_user_id,
    ).first()

    # 3. Read the recipient's saved delivery/read checkpoints.
    last_delivered_id = (
        other_participant.last_delivered_message_id
        if other_participant
        else None
    )
    last_read_id = (
        other_participant.last_read_message_id
        if other_participant
        else None
    )

    # 4. Load messages in chronological order.
    messages = db.query(Message).filter(
        Message.conversation_id == conversation_id
    ).order_by(Message.id.asc()).all()

    # 5. Return each message with its persisted status.
    result = []

    for message in messages:
        sender = db.query(User).filter(
            User.id == message.sender_id
        ).first()

        status = None

        # Status ticks are relevant to messages sent by the current user.
        if message.sender_id == current_user_id:
            if (
                last_read_id is not None
                and message.id <= last_read_id
            ):
                status = "read"
            elif (
                last_delivered_id is not None
                and message.id <= last_delivered_id
            ):
                status = "received"
            else:
                status = "sent"

        result.append({
            "message_id": message.id,
            "conversation_id": message.conversation_id,
            "sender": sender.username if sender else None,
            "content": message.content,
            "created_at": message.created_at,
            "status": status,
        })

    return result


# ==================================================
# WebSocket
# ==================================================

@app.websocket("/ws")
async def websocket_endpoint(
    websocket: WebSocket
):

    # ==================================================
    # Get token
    # ==================================================

    token = websocket.query_params.get(
        "token"
    )

    if token is None:
        print("WS REJECTED: missing token")
        await websocket.close(
            code=1008
        )
        return


    # ==================================================
    # Verify token
    # ==================================================

    user_id = verify_access_token(
        token
    )

    if user_id is None:
        print("WS REJECTED: invalid or expired token")
        await websocket.close(
            code=1008
        )
        return


    # ==================================================
    # Get current user
    # ==================================================

    db = SessionLocal()

    try:

        user = db.get(
            User,
            user_id
        )

        if user is None:
            await websocket.close(
                code=1008
            )
            return

        # VERY IMPORTANT:
        # Extract username while session is open.
        username = user.username

    finally:

        db.close()


    # ==================================================
    # Accept WebSocket
    # ==================================================

    await websocket.accept()
    print(
        f"[WS CONNECTED] username={username} "
        f"server_port={websocket.scope.get('server', ('unknown', 0))[1]}"
    )


    # ==================================================
    # Prevent duplicate connection
    # ==================================================

    if username in connected_users:
        print(f"WS REJECTED: duplicate connection for {username}")
        await websocket.close(
            code=1008
        )

        return


    # ==================================================
    # Create session checkpoint storage
    # ==================================================

    session_checkpoints = {}


    connected_users[username] = {
    "websocket": websocket,
    "user_id": user_id,
    "checkpoints": session_checkpoints
}

    set_user_online(user_id)

    await broadcast_presence(
        username,
        "online"
    )

    heartbeat_task = asyncio.create_task(
        presence_heartbeat(user_id)
    )

    try:

        # ==================================================
        # SEND UNDELIVERED MESSAGES
        # ==================================================

        db = SessionLocal()

        try:

            participants = (
                get_user_participants(
                    db,
                    user_id
                )
            )

            for participant in participants:

                conversation_id = (
                    participant.conversation_id
                )

                last_delivered = (
                    participant
                    .last_delivered_message_id
                )

                session_checkpoints[
                    conversation_id
                ] = last_delivered


                messages = (
                    get_undelivered_messages(
                        db,
                        conversation_id,
                        last_delivered
                    )
                )


                for message in messages:

                    # ----------------------------------
                    # Get sender
                    # ----------------------------------

                    sender = db.get(
                        User,
                        message.sender_id
                    )

                    if sender is None:
                        continue


                    sender_username = (
                        sender.username
                    )


                    # ----------------------------------
                    # Get other participant
                    # ----------------------------------

                    other_participant = (
                        db.query(
                            ConversationParticipant
                        )
                        .filter(
                            ConversationParticipant
                            .conversation_id
                            == conversation_id,

                            ConversationParticipant
                            .user_id
                            != user_id
                        )
                        .first()
                    )

                    if other_participant is None:
                        continue


                    other_user = db.get(
                        User,
                        other_participant.user_id
                    )

                    if other_user is None:
                        continue


                    other_username = (
                        other_user.username
                    )


                    # ----------------------------------
                    # Extract message values
                    # ----------------------------------

                    message_id = message.id
                    message_content = (
                        message.content
                    )
                    message_conversation_id = (
                        message.conversation_id
                    )


                    # ----------------------------------
                    # Build WebSocket message
                    # ----------------------------------

                    message_data = {
                        "sender":
                            sender_username,

                        "recipient":
                            other_username,

                        "content":
                            message_content,

                        "message_id":
                            message_id,

                        "conversation_id":
                            message_conversation_id
                    }


                    await websocket.send_text(
                        json.dumps(
                            message_data
                        )
                    )


                    session_checkpoints[
                        conversation_id
                    ] = message_id

        finally:

            db.close()


        # ==================================================
        # MAIN WEBSOCKET LOOP
        # ==================================================

        while True:

            raw_data = (
                await websocket.receive_text()
            )

            data = json.loads(
                raw_data
            )
            # ------------------------------------------
            # Handle message receipt acknowledgements
            # ------------------------------------------
            event_type = data.get("type")

            if event_type in ("message_received", "message_read"):
                try:
                    message_id = int(data.get("message_id"))
                    conversation_id = int(data.get("conversation_id"))
                except (TypeError, ValueError):
                    continue

                db = SessionLocal()

                try:
                    # The message must exist in this conversation.
                    target_message = db.query(Message).filter(
                        Message.id == message_id,
                        Message.conversation_id == conversation_id
                    ).first()

                    if target_message is None:
                        continue

                    # Only a recipient can acknowledge this message.
                    if target_message.sender_id == user_id:
                        continue

                    # The authenticated user must be a participant.
                    recipient_participant = db.query(
                        ConversationParticipant
                    ).filter(
                        ConversationParticipant.conversation_id
                        == conversation_id,
                        ConversationParticipant.user_id == user_id
                    ).first()

                    if recipient_participant is None:
                        continue

                    # Find the original sender.
                    sender = db.get(User, target_message.sender_id)

                    if sender is None:
                        continue

                    sender_username = sender.username

                    if event_type == "message_received":
                        current_id = (
                            recipient_participant.last_delivered_message_id
                        )

                        if current_id is None or message_id > current_id:
                            update_last_delivered_message(
                                db,
                                conversation_id,
                                user_id,
                                message_id
                            )

                        status = "received"

                    else:
                        current_id = (
                            recipient_participant.last_read_message_id
                        )

                        if current_id is None or message_id > current_id:
                            update_last_read_message(
                                db,
                                conversation_id,
                                user_id,
                                message_id
                            )

                        status = "read"

                finally:
                    db.close()

                await notify_message_status(
                    sender_username,
                    message_id,
                    conversation_id,
                    status
                )

                continue

            # ----------------------------------------------
            # Validate input
            # ----------------------------------------------

            recipient = data.get(
                "recipient"
            )

            message_content = data.get(
                "content"
            )


            if not recipient:
                continue


            if not message_content:
                continue


            message_content = (
                message_content.strip()
            )


            if not message_content:
                continue


            # ==================================================
            # Database operation
            # ==================================================

            db = SessionLocal()

            try:

                # ------------------------------------------
                # Find recipient
                # ------------------------------------------

                recipient_user = (
                    get_user_by_username(
                        db,
                        recipient
                    )
                )


                if recipient_user is None:
                    continue


                # ------------------------------------------
                # IMPORTANT:
                # Extract primitive values NOW.
                # ------------------------------------------

                recipient_id = (
                    recipient_user.id
                )

                recipient_username = (
                    recipient_user.username
                )


                # ------------------------------------------
                # Find/create conversation
                # ------------------------------------------

                conversation = (
                    get_or_create_conversation(
                        db,
                        user_id,
                        recipient_id
                    )
                )


                # ------------------------------------------
                # Extract conversation ID while
                # session is open.
                # ------------------------------------------

                conversation_id = (
                    conversation.id
                )


                # ------------------------------------------
                # Save message
                # ------------------------------------------

                saved_message = (
                    send_message(
                        db,
                        conversation_id,
                        user_id,
                        message_content
                    )
                )


                # ------------------------------------------
                # Extract ALL message values while
                # session is still open.
                # ------------------------------------------

                saved_message_id = (
                    saved_message.id
                )

                saved_content = (
                    saved_message.content
                )

                saved_conversation_id = (
                    saved_message.conversation_id
                )

            finally:

                db.close()


            # ==================================================
            # Database session is CLOSED here.
            #
            # From this point onward we use ONLY normal
            # Python values, NOT SQLAlchemy objects.
            # ==================================================


            message_data = {

                "sender":
                    username,

                "recipient":
                    recipient_username,

                "content":
                    saved_content,

                "message_id":
                    saved_message_id,

                "conversation_id":
                    saved_conversation_id
            }


            message_json = json.dumps(
                message_data
            )


            # ==================================================
            # SEND TO RECIPIENT
            # ==================================================
# ==================================================
# PUBLISH MESSAGE TO REDIS
# ==================================================
            await asyncio.to_thread(
                publish_chat_message,
                {
                    "type": "chat_message",
                    **message_data,
                },
            )



            # ==================================================
            # SEND BACK TO SENDER
            # ==================================================

            if username in connected_users:

                sender_session = (
                    connected_users[
                        username
                    ]
                )


                sender_websocket = (
                    sender_session[
                        "websocket"
                    ]
                )


                try:

                    await sender_websocket.send_text(
                        message_json
                    )

                except WebSocketDisconnect:

                    raise


    # ==================================================
    # WebSocket disconnected
    # ==================================================

    except WebSocketDisconnect:
        heartbeat_task.cancel()
        session = connected_users.get(
            username
        )


        if session:

            checkpoints = (
                session[
                    "checkpoints"
                ]
            )


            db = SessionLocal()

            try:

                for (
                    conversation_id,
                    last_message_id
                ) in checkpoints.items():

                    if (
                        last_message_id
                        is not None
                    ):

                        update_last_delivered_message(
                            db,
                            conversation_id,
                            user_id,
                            last_message_id
                        )

            finally:

                db.close()


        connected_users.pop(username, None)

        set_user_offline(user_id)

        last_seen = set_last_seen(user_id)

        await broadcast_presence(
            username,
            "offline",
            last_seen
        )


    # ==================================================
    # Other WebSocket errors
    # ==================================================

    except Exception as error:
        heartbeat_task.cancel()
        print(
            f"WebSocket error for "
            f"{username}: {error}"
        )

        connected_users.pop(username, None)

        set_user_offline(user_id)

        last_seen = set_last_seen(user_id)

        await broadcast_presence(
            username,
            "offline",
            last_seen
        )