import pytest
import requests

from proxay.server import RecordReplayServer


@pytest.mark.asyncio
async def test_tape_switching_api(backend_server_url, proxay_server_runner, fake_redis):
    """
    Tests that the /__proxay/tape endpoint can switch tapes and modes.
    """
    proxay_port = 9004
    default_tape = "default_tape"

    # 1. Start in record mode on a default tape
    server = RecordReplayServer(
        initial_mode="record",
        tape_dir="tapes",
        default_tape_name=default_tape,
        host=backend_server_url,
        redis_client=fake_redis,
    )
    server.load_tape(default_tape)
    proxay_url = proxay_server_runner(server, proxay_port)

    # Record a request to the default tape
    requests.get(f"{proxay_url}/default")
    assert fake_redis.exists(default_tape)
    assert fake_redis.llen(default_tape) == 1

    # 2. Switch to a new tape via the API
    new_tape = "new_tape"
    switch_payload = {"tape": new_tape}
    response = requests.post(f"{proxay_url}/__proxay/tape", json=switch_payload)
    assert response.status_code == 200
    assert response.text == f"Updated tape: {new_tape}"

    # The new tape should be empty
    assert not fake_redis.exists(new_tape)

    # 3. Record a request to the new tape
    requests.get(f"{proxay_url}/new")
    assert fake_redis.exists(new_tape)
    assert fake_redis.llen(new_tape) == 1
    # The default tape should be unchanged
    assert fake_redis.llen(default_tape) == 1

    # 4. Switch mode to replay via the API
    mode_switch_payload = {"tape": new_tape, "mode": "replay"}
    response = requests.post(f"{proxay_url}/__proxay/tape", json=mode_switch_payload)
    assert response.status_code == 200

    # 5. Verify replay works on the new tape
    replay_response = requests.get(f"{proxay_url}/new")
    assert replay_response.status_code == 200
    assert replay_response.headers["x-original-path"] == "/new"

    # And that requests to the default tape's path now fail
    fail_response = requests.get(f"{proxay_url}/default")
    assert fail_response.status_code == 500
