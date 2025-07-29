import pytest
import requests

from proxay.server import RecordReplayServer


@pytest.mark.asyncio
async def test_replay_simple_get_request(backend_server_url, proxay_server_runner, fake_redis):
    """
    Tests that a recorded request is correctly replayed.
    """
    proxay_port = 9002
    namespace = "test-replay-ns"
    tape_name = "test_replay"
    full_tape_name = f"{namespace}:{tape_name}"
    path = "/replay-test"

    # 1. First, RECORD a tape
    record_server = RecordReplayServer(
        initial_mode="record",
        tape_namespace=namespace,
        default_tape_name=full_tape_name,
        host=backend_server_url,
        redis_client=fake_redis,
    )
    record_server.load_tape(full_tape_name)
    proxay_url = proxay_server_runner(record_server, proxay_port)

    # Make a request to record it
    response = requests.get(f"{proxay_url}{path}?param=1")
    assert response.status_code == 200

    # 2. Switch to REPLAY mode
    switch_to_replay_payload = {"mode": "replay"}
    switch_response = requests.post(f"{proxay_url}/__proxay/tape", json=switch_to_replay_payload)
    assert switch_response.status_code == 200

    # 3. Make the same request again in replay mode
    replay_response = requests.get(f"{proxay_url}{path}?param=1")
    assert replay_response.status_code == 200
    assert replay_response.headers["X-Original-Path"] == path

    # 4. Verify that a non-recorded request fails
    non_recorded_response = requests.get(f"{proxay_url}/not-recorded")
    assert non_recorded_response.status_code == 500
    assert "No matching record found" in non_recorded_response.text
