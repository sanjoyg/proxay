import pytest
import requests

from proxay.server import RecordReplayServer, DEFAULT_TAPE_NAMESPACE


@pytest.mark.asyncio
async def test_tape_switching_api(backend_server_url, proxay_server_runner, fake_redis):
    """
    Tests that the /__proxay/tape endpoint can switch tapes and modes.
    """
    proxay_port = 9004
    default_tape = "default_tape"
    full_default_tape = f"{DEFAULT_TAPE_NAMESPACE}:{default_tape}"

    # 1. Start in record mode on a default tape
    server = RecordReplayServer(
        initial_mode="record",
        default_tape_name=default_tape,
        host=backend_server_url,
        redis_client=fake_redis,
    )
    proxay_url = proxay_server_runner(server, proxay_port)

    # Record a request to the default tape
    requests.get(f"{proxay_url}/default")
    assert fake_redis.exists(full_default_tape)
    assert fake_redis.llen(full_default_tape) == 1

    # 2. Switch to a new tape via the API
    new_tape = "new_tape"
    full_new_tape = f"{DEFAULT_TAPE_NAMESPACE}:{new_tape}"
    switch_payload = {"tape": new_tape}
    response = requests.post(f"{proxay_url}/__proxay/tape", json=switch_payload)
    assert response.status_code == 200
    assert response.text == f"Updated tape: {full_new_tape}"

    assert not fake_redis.exists(full_new_tape)

    # 3. Record a request to the new tape
    requests.get(f"{proxay_url}/new")
    assert fake_redis.exists(full_new_tape)
    assert fake_redis.llen(full_new_tape) == 1
    assert fake_redis.llen(full_default_tape) == 1

    # 4. Switch mode to replay via the API
    mode_switch_payload = {"tape": new_tape, "mode": "replay"}
    response = requests.post(f"{proxay_url}/__proxay/tape", json=mode_switch_payload)
    assert response.status_code == 200

    # 5. Verify replay works on the new tape
    replay_response = requests.get(f"{proxay_url}/new")
    assert replay_response.status_code == 200
    assert replay_response.headers["x-original-path"] == "/new"

    fail_response = requests.get(f"{proxay_url}/default")
    assert fail_response.status_code == 500
