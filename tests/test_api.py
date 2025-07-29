import pytest
import requests

from proxay.server import RecordReplayServer


@pytest.mark.asyncio
async def test_tape_switching_api(backend_server_url, proxay_server_runner, fake_redis):
    """
    Tests that the /__proxay/tape endpoint can switch tapes and modes.
    """
    proxay_port = 9004
    namespace = "test-api-ns"
    default_tape_short_name = "default_tape"
    default_tape_full_name = f"{namespace}:{default_tape_short_name}"

    # 1. Start in record mode on a default tape
    server = RecordReplayServer(
        initial_mode="record",
        tape_namespace=namespace,
        default_tape_name=default_tape_full_name,
        host=backend_server_url,
        redis_client=fake_redis,
    )
    server.load_tape(default_tape_full_name)
    proxay_url = proxay_server_runner(server, proxay_port)

    # Record a request to the default tape
    requests.get(f"{proxay_url}/default")
    assert fake_redis.exists(default_tape_full_name)
    assert fake_redis.llen(default_tape_full_name) == 1

    # 2. Switch to a new tape via the API
    new_tape_short_name = "new_tape"
    new_tape_full_name = f"{namespace}:{new_tape_short_name}"
    switch_payload = {"tape": new_tape_short_name}
    response = requests.post(f"{proxay_url}/__proxay/tape", json=switch_payload)
    assert response.status_code == 200
    assert response.text == f"Updated tape: {new_tape_full_name}"

    assert not fake_redis.exists(new_tape_full_name)

    # 3. Record a request to the new tape
    requests.get(f"{proxay_url}/new")
    assert fake_redis.exists(new_tape_full_name)
    assert fake_redis.llen(new_tape_full_name) == 1
    assert fake_redis.llen(default_tape_full_name) == 1

    # 4. Switch mode to replay via the API
    mode_switch_payload = {"tape": new_tape_short_name, "mode": "replay"}
    response = requests.post(f"{proxay_url}/__proxay/tape", json=mode_switch_payload)
    assert response.status_code == 200

    # 5. Verify replay works on the new tape
    replay_response = requests.get(f"{proxay_url}/new")
    assert replay_response.status_code == 200
    assert replay_response.headers["x-original-path"] == "/new"

    fail_response = requests.get(f"{proxay_url}/default")
    assert fail_response.status_code == 500
