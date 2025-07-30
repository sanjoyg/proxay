import pytest
import requests
import yaml

from proxay.server import RecordReplayServer, DEFAULT_TAPE_NAMESPACE


@pytest.mark.asyncio
async def test_tape_switching_api(backend_server_url, proxay_server_runner, fake_redis):
    """
    Tests that the /__proxay/tape endpoint can switch tapes and modes.
    """
    proxay_port = 9004
    default_tape = "default_tape"
    full_default_tape = f"{DEFAULT_TAPE_NAMESPACE}:{default_tape}"

    server = RecordReplayServer(
        initial_mode="record",
        default_tape_name=default_tape,
        host=backend_server_url,
        redis_client=fake_redis,
    )
    proxay_url = proxay_server_runner(server, proxay_port)

    requests.get(f"{proxay_url}/default")
    assert fake_redis.exists(full_default_tape)
    tape_yaml = fake_redis.get(full_default_tape)
    assert len(yaml.safe_load(tape_yaml)["http_interactions"]) == 1

    new_tape = "new_tape"
    full_new_tape = f"{DEFAULT_TAPE_NAMESPACE}:{new_tape}"
    switch_payload = {"tape": new_tape}
    response = requests.post(f"{proxay_url}/__proxay/tape", json=switch_payload)
    assert response.status_code == 200

    requests.get(f"{proxay_url}/new")
    assert fake_redis.exists(full_new_tape)
    new_tape_yaml = fake_redis.get(full_new_tape)
    assert len(yaml.safe_load(new_tape_yaml)["http_interactions"]) == 1

    mode_switch_payload = {"tape": new_tape, "mode": "replay"}
    response = requests.post(f"{proxay_url}/__proxay/tape", json=mode_switch_payload)
    assert response.status_code == 200

    replay_response = requests.get(f"{proxay_url}/new")
    assert replay_response.status_code == 200
    assert replay_response.headers["x-original-path"] == "/new"

    fail_response = requests.get(f"{proxay_url}/default")
    assert fail_response.status_code == 500
