import base64

import msgpack
import pytest
import requests

from proxay.server import RecordReplayServer


@pytest.mark.asyncio
async def test_record_simple_get_request(backend_server_url, proxay_server_runner, fake_redis):
    """
    Tests that a simple GET request is recorded correctly using the
    MessagePack and Redis List storage format with a bytes-based client.
    """
    # 1. Setup Proxay in record mode
    proxay_port = 9001
    tape_name = "test_record_msgpack_bytes"

    server = RecordReplayServer(
        initial_mode="record",
        tape_dir="tapes",
        default_tape_name=tape_name,
        host=backend_server_url,
        redact_headers=["user-agent", "accept-encoding"],
        redis_client=fake_redis,
    )
    server.load_tape(tape_name)

    proxay_url = proxay_server_runner(server, proxay_port)

    # 2. Make a request to proxay
    path = "/hello"
    headers = {"X-Test-Header": "test-value"}
    response = requests.get(f"{proxay_url}{path}", headers=headers)

    assert response.status_code == 200
    assert response.text == "world"

    # 3. Verify the tape was saved to Redis correctly
    assert fake_redis.exists(tape_name)
    assert fake_redis.type(tape_name) == b'list'

    tape_data_raw = fake_redis.lrange(tape_name, 0, -1)
    assert len(tape_data_raw) == 1

    # Deserialize the first record from MessagePack
    # Use raw=False to decode keys and strings to UTF-8
    interaction = msgpack.unpackb(tape_data_raw[0], raw=False)

    # Verify request data
    request_data = interaction["request"]
    assert request_data["method"] == "GET"
    assert request_data["path"] == "/hello"

    req_headers = request_data["headers"]
    assert req_headers["x-test-header"] == "test-value"
    assert req_headers["user-agent"] == "XXXX"

    # Verify response data
    response_data = interaction["response"]
    assert response_data["status"]["code"] == 200

    body_data = response_data["body"]
    assert body_data["encoding"] == "base64"

    decoded_body = base64.b64decode(body_data["data"])
    assert decoded_body == b"world"

    resp_headers = response_data["headers"]
    assert resp_headers["x-test-header"] == "test-value"
