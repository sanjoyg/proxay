# Proxay (Python Edition)

[![CircleCI](https://circleci.com/gh/airtasker/proxay.svg?style=svg)](https://circleci.com/gh/airtasker/proxay)

Proxay (pronounced "prokseï") is a proxy server that helps you write faster tests. This is a full port of the original Node.js Proxay to Python 3, with an optimized, Redis-based backend for tape persistence.

## Features
- **Record mode**: Proxies requests to a backend and records interactions as "tapes" in a Redis database.
- **Replay mode**: Replays requests from your "tapes" in Redis, no backend necessary.
- **Mimic mode**: Records requests the first time, then replays them on subsequent calls.
- **Passthrough mode**: A conventional proxy that doesn't persist anything.
- **Optimized Storage**: Uses MessagePack for fast serialization and Redis Lists for efficient storage.
- **Verbose Stats**: In mimic mode, provides console stats on cache hits/misses when run with `--verbose`.

## Prerequisites
- Docker and Docker Compose

## Running with Docker Compose (Recommended)

The easiest way to run Proxay and its Redis dependency is with Docker Compose.

1.  **Modify the command in `docker-compose.yml`:**
    Open the `docker-compose.yml` file and edit the `command` section to suit your needs (e.g., change the `--host`, `--mode`, etc.).

2.  **Run the services:**
    ```sh
    docker-compose up --build
    ```
    This will build the Proxay image, start both the Proxay and Redis containers, and connect them.

## Advanced Usage (without Docker Compose)

### Running with Docker

1.  **Build the Docker image:**
    ```sh
    docker build -t proxay .
    ```

2.  **Run the container:**
    ```sh
    docker run --rm -it --network=host proxay \
        --mode record \
        --host http://localhost:8080 \
        --redis-host localhost
    ```

### Testing

A dedicated test container can be used to run all tests.

1.  **Build the test image:**
    ```sh
    docker build -f Dockerfile.test -t proxay-test .
    ```

2.  **Run the tests:**
    ```sh
    docker run --rm -it proxay-test
    ```

## Options
- `--host`: The target host to proxy requests to.
- `--port`: The local port for Proxay to run on (default: `3000`).
- `--default-tape`: The name of the default tape to use (default: `default`).
- `--redis-host`: The Redis server host (default: `localhost`).
- `--redis-port`: The Redis server port (default: `6379`).
- `-v`, `--verbose`: Enable verbose logging, including mimic mode stats.
- `-r, --redact-headers`: Comma-separated list of request headers to redact.
- `--ignore-headers`: Comma-separated list of headers to ignore during matching.
- `--exact-request-matching`: Disables fuzzy matching.
- `--send-proxy-port`: Forwards Proxay's port in the `Host` header.
- `--debug-matcher-fails`: Provides debug information on failed matches.
