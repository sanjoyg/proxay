import base64

import msgpack
import pytest
import requests

from proxay.server import RecordReplayServer


@pytest.mark.asyncio
async def test_record_simple_get_request(backend_server_url, proxay_server_runner, fake_redis):
    """
    Tests that a simple GET request is recorded correctly.
    """
    proxay_port = 9001
    namespace = "test-ns"
    tape_name = "test_record"
    full_tape_name = f"{namespace}:{tape_name}"

    server = RecordReplayServer(
        initial_mode="record",
        tape_namespace=namespace,
        default_tape_name=full_tape_name,
        host=backend_server_url,
        redact_headers=["user-agent", "accept-encoding"],
        redis_client=fake_redis,
    )
    server.load_tape(full_tape_name)

    proxay_url = proxay_server_runner(server, proxay_port)

    path = "/hello"
    headers = {"X-Test-Header": "test-value"}
    response = requests.get(f"{proxay_url}{path}", headers=headers)

    assert response.status_code == 200
    assert response.text == "world"

    assert fake_redis.exists(full_tape_name)
    assert fake_redis.type(full_tape_name) == b'list'

    tape_data_raw = fake_redis.lrange(full_tape_name, 0, -1)
    assert len(tape_data_raw) == 1

    interaction = msgpack.unpackb(tape_data_raw[0], raw=False)

    request_data = interaction["request"]
    assert request_data["method"] == "GET"
    assert request_data["path"] == "/hello"

    req_headers = request_data["headers"]
    assert req_headers["x-test-header"] == "test-value"
    assert req_headers["user-agent"] == "XXXX"

    response_data = interaction["response"]
    assert response_data["status"]["code"] == 200

    body_data = response_data["body"]
    assert body_data["encoding"] == "base64"

    decoded_body = base64.b64decode(body_data["data"])
    assert decoded_body == b"world"

    resp_headers = response_data["headers"]
    assert resp_headers["x-test-header"] == "test-value"
