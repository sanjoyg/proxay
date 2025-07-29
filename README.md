# Proxay (Python Edition)

[![CircleCI](https://circleci.com/gh/airtasker/proxay.svg?style=svg)](https://circleci.com/gh/airtasker/proxay)

Proxay (pronounced "prokseï") is a proxy server that helps you write faster tests. This is a full port of the original Node.js Proxay to Python 3, with an optimized, Redis-based backend for tape persistence.

## Features
- **Record mode**: Proxies requests to a backend and records interactions as "tapes" in a Redis database.
- **Replay mode**: Replays requests from your "tapes" in Redis, no backend necessary.
- **Mimic mode**: Records requests the first time, then replays them on subsequent calls.
- **Passthrough mode**: A conventional proxy that doesn't persist anything.
- **Optimized Storage**: Uses MessagePack for fast serialization and Redis Lists for efficient storage, making it much more performant than the original YAML-based file storage.

## Prerequisites

- Python 3.9+ (for local development)
- Docker and Docker Compose (for containerized deployment)
- A running [Redis](https://redis.io/) instance.

## Running with Docker (Recommended)

The easiest way to run Proxay is with Docker.

1.  **Build the Docker image:**
    ```sh
    docker build -t proxay .
    ```

2.  **Run the container:**

    You need to connect the container to the same network as your backend service and Redis. Using `--network=host` is often the simplest way for local development.

    ```sh
    # Example: Record mode
    docker run --rm -it --network=host proxay \
        --mode record \
        --host http://localhost:8080 \
        --tapes-dir my-app-tapes \
        --redis-host localhost
    ```
    *Note: If your backend is running on the host machine from the container's perspective, you might need to use `http://host.docker.internal:PORT` instead of `http://localhost:PORT` for the `--host` argument, depending on your Docker setup.*

## Local Development Setup

If you prefer to run the application locally without Docker:

1.  **Create a virtual environment:**
    ```sh
    python -m venv .venv
    source .venv/bin/activate
    ```

2.  **Install dependencies:**
    ```sh
    pip install -r requirements.txt
    ```

3.  **Run the application:**
    The main command is run via `python -m src.proxay.cli`.
    ```sh
    # Example: Record mode
    PYTHONPATH=src python -m src.proxay.cli \
        --mode record \
        --host http://localhost:8080 \
        --tapes-dir my-app-tapes
    ```

## Specifying a Tape

You can dynamically switch tapes and modes by sending a `POST` request to the `/__proxay/tape` endpoint:
```json
{
  "tape": "test-suite/my-specific-test",
  "mode": "replay"
}
```

## Options
- `--host`: The target host to proxy requests to (e.g., `https://api.example.com`).
- `--port`: The local port for Proxay to run on (default: `3000`).
- `--tapes-dir`: A required namespace for your tapes in Redis.
- `--redis-host`: The Redis server host (default: `localhost`).
- `--redis-port`: The Redis server port (default: `6379`).
- `--send-proxy-port`: Forwards Proxay's port in the `Host` header.
- `--exact-request-matching`: Disables fuzzy matching and only replays exact matches.
- `-r, --redact-headers`: A comma-separated list of request headers to redact (replace with `XXXX`).
- `--ignore-headers`: A comma-separated list of headers to ignore during matching.
