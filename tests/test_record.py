import pytest
import requests
import yaml

from proxay.server import RecordReplayServer


@pytest.mark.asyncio
async def test_record_simple_get_request(backend_server_url, proxay_server_runner, fake_redis):
    """
    Tests that a simple GET request is recorded correctly.
    """
    # 1. Setup Proxay in record mode
    proxay_port = 9001
    tape_name = "test_record_simple_get"

    server = RecordReplayServer(
        initial_mode="record",
        tape_dir="tapes",
        default_tape_name=tape_name,
        host=backend_server_url,
        redact_headers=["user-agent", "accept-encoding"],
        redis_client=fake_redis,  # Inject the fake redis client
    )
    # Manually load the tape to initialize, since we are not using the CLI's startup logic
    server.load_tape(tape_name)

    proxay_url = proxay_server_runner(server, proxay_port)

    # 2. Make a request to proxay
    path = "/hello"
    headers = {"X-Test-Header": "test-value"}
    response = requests.get(f"{proxay_url}{path}", headers=headers)

    assert response.status_code == 200
    assert response.text == "world"
    assert "x-original-method" in response.headers
    assert response.headers["x-original-method"] == "GET"

    # 3. Verify the tape was saved to Redis correctly
    assert fake_redis.exists(tape_name)
    tape_yaml = fake_redis.get(tape_name)
    tape_data = yaml.safe_load(tape_yaml)

    interactions = tape_data["http_interactions"]
    assert len(interactions) == 1

    # Verify request data
    request_data = interactions[0]["request"]
    assert request_data["method"] == "GET"
    assert request_data["path"] == path
    assert request_data["headers"]["x-test-header"] == "test-value"
    assert request_data["headers"]["user-agent"] == "XXXX"  # Check redaction

    # Verify response data
    response_data = interactions[0]["response"]
    assert response_data["status"]["code"] == 200
    assert response_data["body"]["encoding"] == "utf8"
    assert response_data["body"]["data"] == "world"
    assert "x-test-header" in response_data["headers"]
    assert response_data["headers"]["x-test-header"] == "test-value"
