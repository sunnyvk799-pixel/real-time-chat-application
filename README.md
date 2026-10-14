# Real-Time Chat Application

A real-time messaging application built with React, TypeScript, FastAPI, PostgreSQL, and Redis. The project explores WebSocket communication, JWT-based authentication, persistent message storage, delivery and read checkpoints, and cross-instance message delivery using Redis Pub/Sub.

## Key Features

- **User authentication:** User registration and login with password hashing and JWT-based authentication.
- **Real-time messaging:** WebSocket connections for sending and receiving messages.
- **Persistent storage:** PostgreSQL for users, conversations, participants, and messages.
- **Cross-instance message delivery:** Redis Pub/Sub to distribute chat events across backend instances.
- **Conversation management:** Retrieve user conversations and message history.
- **Message status tracking:** Delivery and read checkpoints for conversations.
- **Connection management:** WebSocket connection handling, heartbeat monitoring, and disconnect cleanup.
- **Database migrations:** Alembic migrations for evolving the database schema.
- **Automated testing:** Pytest tests covering authentication, messaging, WebSockets, message checkpoints, and Redis-related behavior.
- **Load balancing:** NGINX configured to distribute traffic across multiple FastAPI instances during local testing.

## Tech Stack

| Component | Technologies |
|---|---|
| Frontend | React, TypeScript, Vite |
| Backend | Python, FastAPI |
| API communication | HTTP REST APIs, WebSockets |
| Database | PostgreSQL |
| ORM and migrations | SQLAlchemy, Alembic |
| Authentication | JWT, password hashing |
| Messaging infrastructure | Redis Pub/Sub |
| Reverse proxy and load balancing | NGINX |
| Testing | Pytest |

## Architecture

The application separates the frontend, API backend, persistent storage, and messaging infrastructure.

```text
React + TypeScript Frontend
            |
            v
      NGINX Proxy
            |
       +----+----+
       |         |
       v         v
   FastAPI    FastAPI
   Instance 1 Instance 2
       |         |
       +----+----+
            |
       +----+-----+
       |          |
       v          v
   PostgreSQL    Redis
   Persistent    Pub/Sub
   Data          Events
```

Redis Pub/Sub enables backend instances to exchange chat events. PostgreSQL stores application data independently of individual WebSocket connections.

## Project Structure

```text
real-time-chat-project/
├── backend/
│   ├── alembic/
│   │   └── versions/
│   ├── tests/
│   ├── auth.py
│   ├── conversation.py
│   ├── database.py
│   ├── main.py
│   ├── message.py
│   ├── models.py
│   ├── redis_client.py
│   ├── redis_pubsub.py
│   ├── schemas.py
│   └── requirements.txt
├── frontend/
│   ├── src/
│   ├── package.json
│   └── vite.config.ts
└── README.md
```

## Prerequisites

Before running the application locally, install:

- Python
- Node.js and npm
- PostgreSQL
- Redis, or a compatible local Redis service
- Git

NGINX is needed when reproducing the load-balanced setup.

## Local Development Setup

### 1. Clone the repository

```bash
git clone https://github.com/sunnyvk799-pixel/real-time-chat-application.git
cd real-time-chat-application
```

### 2. Configure the backend

```bash
cd backend
python -m venv .venv
```

Activate the virtual environment on Windows:

```powershell
.\.venv\Scripts\Activate.ps1
```

Install the dependencies:

```bash
python -m pip install -r requirements.txt
```

Configure the required environment variables for your local PostgreSQL database, Redis service, and authentication settings. Keep real credentials and secrets in your local `.env` file; never commit them to GitHub.

### 3. Set up the database

Create a local PostgreSQL database and configure the backend connection string.

Apply the Alembic migrations using the configuration appropriate for your project:

```bash
alembic upgrade head
```

Run this command from the backend directory after configuring the database connection.

### 4. Start the backend

From the backend directory:

```bash
python -m uvicorn main:app --reload --port 8000
```

The backend will listen on port `8000`.

### 5. Start the frontend

Open another terminal:

```bash
cd frontend
npm install
npm run dev
```

Use the local URL printed by Vite to open the frontend.

Ensure that the frontend API and WebSocket URLs match your local backend or NGINX configuration.

## Testing

The backend uses pytest for automated tests.

From the backend directory:

```bash
python -m pytest -q
```

The test suite covers areas including authentication, registration, conversations, message retrieval, delivery and read checkpoints, WebSocket behavior, and Redis Pub/Sub.

The project has also been tested locally with two separate backend instances to verify cross-instance WebSocket message delivery through Redis Pub/Sub.

Run the tests against a dedicated test database. Do not point the test suite at a database containing development or production data.

## Engineering Focus

This project explores several backend and distributed-systems concepts:

- Stateful WebSocket connections and connection lifecycle management.
- Authentication for HTTP endpoints and WebSocket connections.
- Persistent data modeling and schema migrations.
- Redis Pub/Sub for cross-instance event distribution.
- Message delivery and read-state tracking.
- Reverse proxying and multi-instance backend testing.
- Automated tests for application behavior and integration points.

## Roadmap

- [ ] Containerize the frontend and backend with Docker.
- [ ] Add Docker Compose for the application and its dependencies.
- [ ] Automate tests and builds with GitHub Actions.
- [ ] Add load and reliability testing for concurrent WebSocket connections.
- [ ] Document deployment, configuration, and operational procedures.
- [ ] Evaluate monitoring, logging, and production security improvements.

## Security

- Keep environment files and credentials out of version control.
- Use strong, unique secrets outside source code.
- Restrict database access and use separate development and test databases.
- Configure HTTPS and secure deployment settings before exposing the application publicly.

## License

Add the license you intend to distribute this project under before publishing a license notice.