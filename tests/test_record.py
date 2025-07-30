import base64
import yaml

import pytest
import requests

from proxay.server import RecordReplayServer, DEFAULT_TAPE_NAMESPACE


@pytest.mark.asyncio
async def test_record_simple_get_request(backend_server_url, proxay_server_runner, fake_redis):
    """
    Tests that a simple GET request is recorded correctly using YAML storage.
    """
    proxay_port = 9001
    tape_name = "test_record_yaml"
    full_tape_name = f"{DEFAULT_TAPE_NAMESPACE}:{tape_name}"

    server = RecordReplayServer(
        initial_mode="record",
        default_tape_name=tape_name,
        host=backend_server_url,
        redact_headers=["user-agent", "accept-encoding"],
        redis_client=fake_redis,
    )

    proxay_url = proxay_server_runner(server, proxay_port)

    path = "/hello"
    headers = {"X-Test-Header": "test-value"}
    response = requests.get(f"{proxay_url}{path}", headers=headers)

    assert response.status_code == 200
    assert response.text == "world"

    # Verify the tape was saved to Redis correctly
    assert fake_redis.exists(full_tape_name)
    assert fake_redis.type(full_tape_name) == b'string'

    tape_yaml = fake_redis.get(full_tape_name)
    tape_data = yaml.safe_load(tape_yaml)

    interactions = tape_data["http_interactions"]
    assert len(interactions) == 1

    # Verify request data
    request_data = interactions[0]["request"]
    assert request_data["method"] == "GET"
    assert request_data["path"] == "/hello"

    req_headers = request_data["headers"]
    assert req_headers["x-test-header"] == "test-value"
    assert req_headers["user-agent"] == "XXXX"

    # Verify response data
    response_data = interactions[0]["response"]
    assert response_data["status"]["code"] == 200

    body_data = response_data["body"]
    assert body_data["encoding"] == "base64"

    decoded_body = base64.b64decode(body_data["data"])
    assert decoded_body == b"world"

    resp_headers = response_data["headers"]
    assert resp_headers["x-test-header"] == "test-value"
