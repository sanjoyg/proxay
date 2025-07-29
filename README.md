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

## Running with Docker (Recommended)

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
        --tape-namespace my-app-tests \
        --redis-host localhost
    ```

## Testing

This project includes a comprehensive test suite.

### Running Tests with Docker (Recommended)

A dedicated test container can be used to run all tests in a clean environment.

1.  **Build the test image:**
    ```sh
    docker build -f Dockerfile.test -t proxay-test .
    ```

2.  **Run the tests:**
    This will run `pytest` and output a coverage report.
    ```sh
    docker run --rm -it proxay-test
    ```

### Running Tests Locally

1.  **Create a virtual environment and install dependencies:**
    ```sh
    python -m venv .venv
    source .venv/bin/activate
    pip install -r requirements.txt -r requirements-dev.txt
    ```

2.  **Run the tests:**
    ```sh
    PYTHONPATH=src pytest --cov=src/proxay
    ```

## Local Development
If you need to run the server outside of Docker for development:

```sh
# Set up environment and install dependencies as per "Running Tests Locally"
# Then run the server:
PYTHONPATH=src python -m src.proxay.cli \
    --mode record \
    --host http://localhost:8080 \
    --tape-namespace my-app-tests
```

## Options
- `--host`: The target host to proxy requests to.
- `--port`: The local port for Proxay to run on (default: `3000`).
- `--tape-namespace`: A required namespace for your tapes in Redis.
- `--default-tape`: The name of the default tape within the namespace (default: `default`).
- `--redis-host`: The Redis server host (default: `localhost`).
- `--redis-port`: The Redis server port (default: `6379`).
- `-r, --redact-headers`: Comma-separated list of request headers to redact.
- `--ignore-headers`: Comma-separated list of headers to ignore during matching.
- `--exact-request-matching`: Disables fuzzy matching.
- `--send-proxy-port`: Forwards Proxay's port in the `Host` header.
- `--debug-matcher-fails`: Provides debug information on failed matches.
