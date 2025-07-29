# Proxay (Python Edition)

[![CircleCI](https://circleci.com/gh/airtasker/proxay.svg?style=svg)](https://circleci.com/gh/airtasker/proxay)

Proxay (pronounced "prokseï") is a proxy server that helps you write faster tests. This is a full port of the original Node.js Proxay to Python 3, with a Redis-based backend for tape persistence.

Use Proxay as a layer between a client and its backend to record interactions and later replay them on demand.

Proxay can operate in several modes:
- **Record mode**: Proxies requests to the backend and records interactions as "tapes" in a Redis database.
- **Replay mode**: Replays requests from your "tapes" in Redis (no backend necessary).
- **Mimic mode**: Records requests the first time it encounters them, then replays them (record then replay).
- **Passthrough mode**: Proxies requests without persisting them (like a conventional proxy).

Proxay is language-agnostic: it's just a server. Your code doesn't need to be written in a specific language to benefit from using it.

## Prerequisites

- Python 3.9+
- A running [Redis](https://redis.io/) instance.

## Installing

It is recommended to install the dependencies in a virtual environment.

```sh
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

## Running

The main command is run via `python -m src.proxay.cli`. You must have a Redis server running.

```sh
# Record mode (proxies requests)
python -m src.proxay.cli --mode record --host https://api.website.com --tapes-dir my-app-tapes

# Replay mode (no proxying)
python -m src.proxay.cli --mode replay --tapes-dir my-app-tapes

# Passthrough mode (proxies requests without persisting)
python -m src.proxay.cli --mode passthrough --host https://api.website.com
```

**Note on `--tapes-dir`**: In this Python version, this parameter is used as a *namespace* for tapes within Redis, not as a filesystem directory. It's a required parameter for any mode that interacts with tapes.

You can also run several instances of Proxay simultaneously on different ports (for example to proxy multiple backends). Just pick a different port (e.g. `--port 3001`).

## Specifying a tape

If you have several tests, you likely want to save recorded interactions into one tape per test, and replay from the correct tape for each test.

You can do this by sending a `POST` request to `/__proxay/tape` with the following payload:
```json
{
  "tape": "test1/my_tape"
}
```

In record mode, this will create a new key `test1/my_tape` in Redis within the namespace defined by `--tapes-dir`. In replay mode, this same key will be read.

## (Some) Options

`--send-proxy-port`: This flag enables the forwarding of the Proxay's local port number to the proxied host in the host header.

`--ignore-headers <headers>`: Allows users to specify a list of headers (comma-separated) that should be ignored by Proxay's matching algorithm during request comparison.

`-r, --redact-headers <headers>`: This option enables the redaction of specific HTTP header values (comma-separated), which are replaced by `XXXX`.

`--debug-matcher-fails`: When exact request matching is enabled, this flag provides some debug information on why a request did not match any recorded tape.

`--redis-host <host>`: Specify the Redis host (default: `localhost`).

`--redis-port <port>`: Specify the Redis port (default: `6379`).

## Typical use case

The use case remains the same as the original Proxay. By recording interactions and replaying them, you can create faster, more stable tests that are independent of a live backend.

---

## Comparison with alternatives

The comparisons with `node-replay`, `yakbak`, `vcr`, and `MockServer` from the original README still apply. Proxay-py's main differentiator is being a standalone proxy server, now powered by Python and Redis.
