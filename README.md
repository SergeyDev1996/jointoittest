# FastAPI WebSocket Notifier

A minimal FastAPI WebSocket server that broadcasts notifications to all connected clients and shuts down gracefully. The app supports multi-worker uvicorn deployments by coordinating connection tracking and broadcasts through Redis.

## Running with Docker Compose
A sample `docker-compose.yml` is provided. From the repository root:
```bash
docker-compose up --build
```
This starts Redis and the FastAPI app together, exposing the server on port 8000.

## Using the WebSocket endpoint
- Connect to `ws://127.0.0.1:8000/ws`
- Every message you send is echoed to **all** connected clients.
- A test notification is broadcast automatically every 10 seconds.

Quick test with [`websocat`](https://github.com/vi/websocat):
```bash
websocat ws://localhost:8000/ws
# Expect periodic "Test Notification" messages; any text you type is rebroadcast to all peers.
```

To test grateful shutdown please execute the following: 
```
docker kill --signal=SIGTERM ws_server
```

## Graceful shutdown logic
- The app listens for `SIGTERM`/`SIGINT`.
- When a signal arrives, shutdown begins but the process stays alive until **either**:
  - All active WebSocket connections across workers reach zero, **or**
  - 30 minutes elapse (configurable via `FORCE_SHUTDOWN_AFTER`).
- Progress is logged every 5 seconds, including active-connection counts and remaining time.
- Broadcast loops are cancelled before exit, and per-worker connection metadata is cleaned up in Redis.
- With multiple uvicorn workers, each worker applies the same shutdown rules while Redis keeps a shared view of active connections so workers do not exit until their clients (or the deadline) allow it.

## Health check
`GET /` returns a simple JSON status indicating the service is running and which worker handled the request.

