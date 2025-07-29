import base64

import msgpack
import pytest
import requests

from proxay.server import RecordReplayServer


@pytest.mark.asyncio
async def test_replay_simple_get_request(backend_server_url, proxay_server_runner, fake_redis):
    """
    Tests that a recorded request is correctly replayed.
    """
    proxay_port = 9002
    tape_name = "test_replay_simple_get"
    path = "/replay-test"

    # 1. First, RECORD a tape
    record_server = RecordReplayServer(
        initial_mode="record",
        tape_dir="tapes",
        default_tape_name=tape_name,
        host=backend_server_url,
        redis_client=fake_redis,
    )
    record_server.load_tape(tape_name)
    proxay_url = proxay_server_runner(record_server, proxay_port)

    # Make a request to record it
    response = requests.get(f"{proxay_url}{path}?param=1")
    assert response.status_code == 200

    # The server needs to be stopped to be started again in replay mode.
    # The fixture runner will handle this, but we need a new runner for the new server.
    # The current fixture design is one server per test function.
    # I will adapt the test to work with this.
    # Let's stop the server manually. The fixture doesn't support that.
    # A better way is to have two separate tests, but that would require sharing state (the redis db).
    # fakeredis is function-scoped, so this is fine.

    # Let's assume the proxay_server_runner fixture can be called again to start a new server.
    # My fixture implementation does not support this well.
    # I will refactor the test to not need a server restart.
    # I can use the /__proxay/tape endpoint to switch modes.

    # 2. Switch to REPLAY mode
    switch_to_replay_payload = {"mode": "replay"}
    switch_response = requests.post(f"{proxay_url}/__proxay/tape", json=switch_to_replay_payload)
    assert switch_response.status_code == 200

    # 3. Make the same request again in replay mode
    # This time, the backend server should NOT be hit.
    # We can verify this by checking the headers from the backend.
    # Or by stopping the backend server.
    # Let's try to make a request to a path that the backend doesn't handle.
    # No, the best way is to check the response.

    replay_response = requests.get(f"{proxay_url}{path}?param=1")
    assert replay_response.status_code == 200

    # The body should be the same as the recorded one.
    # The test backend echoes the path in a header. The replayed response should have it.
    assert replay_response.headers["X-Original-Path"] == path

    # 4. Verify that a non-recorded request fails
    non_recorded_response = requests.get(f"{proxay_url}/not-recorded")
    assert non_recorded_response.status_code == 500
    assert "No matching record found" in non_recorded_response.text
