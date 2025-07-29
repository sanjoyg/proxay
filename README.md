# Proxay (Python Edition)

[![CircleCI](https://circleci.com/gh/airtasker/proxay.svg?style=svg)](https://circleci.com/gh/airtasker/proxay)

Proxay (pronounced "prokseï") is a proxy server that helps you write faster tests. This is a full port of the original Node.js Proxay to Python 3, with an optimized, Redis-based backend for tape persistence.

## Features
- **Record mode**: Proxies requests to a backend and records interactions as "tapes" in a Redis database.
- **Replay mode**: Replays requests from your "tapes" in Redis, no backend necessary.
- **Mimic mode**: Records requests the first time, then replays them on subsequent calls.
- **Passthrough mode**: A conventional proxy that doesn't persist anything.
- **Optimized Storage**: Uses MessagePack for fast serialization and Redis Lists for efficient storage.

## Prerequisites
- Docker and Docker Compose
- A running [Redis](https://redis.io/) instance.

## Development Environment

The recommended way to develop and contribute to this project is by using the provided Dev Container, which can be opened in VS Code.

1.  Make sure you have the [Dev Containers extension](https://marketplace.visualstudio.com/items?itemName=ms-vscode-remote.remote-containers) installed in VS Code.
2.  Open the repository in VS Code.
3.  When prompted, click "Reopen in Container".

This will build the development environment, install all dependencies, and configure your VS Code instance. You can run the server and tests directly from the integrated terminal.

## Running with Docker

1.  **Build the Docker image:**
    ```sh
    docker build -t proxay .
    ```

2.  **Run the container:**
    ```sh
    # Example: Record mode
    docker run --rm -it --network=host proxay \
        --mode record \
        --host http://localhost:8080 \
        --redis-host localhost
    ```

## Testing

### Running Tests with Docker

1.  **Build the test image:**
    ```sh
    docker build -f Dockerfile.test -t proxay-test .
    ```

2.  **Run the tests:**
    ```sh
    docker run --rm -it proxay-test
    ```

### Running Tests Locally

1.  **Set up environment and install dependencies:**
    ```sh
    python -m venv .venv
    source .venv/bin/activate
    pip install -r requirements.txt -r requirements-dev.txt
    ```

2.  **Run the tests:**
    ```sh
    PYTHONPATH=src pytest --cov=src/proxay
    ```

## Options
- `--host`: The target host to proxy requests to.
- `--port`: The local port for Proxay to run on (default: `3000`).
- `--default-tape`: The name of the default tape to use (default: `default`).
- `--redis-host`: The Redis server host (default: `localhost`).
- `--redis-port`: The Redis server port (default: `6379`).
- `-r, --redact-headers`: Comma-separated list of request headers to redact.
- `--ignore-headers`: Comma-separated list of headers to ignore during matching.
- `--exact-request-matching`: Disables fuzzy matching.
- `--send-proxy-port`: Forwards Proxay's port in the `Host` header.
- `--debug-matcher-fails`: Provides debug information on failed matches.
