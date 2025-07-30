import pytest
import requests
import yaml

from proxay.server import RecordReplayServer, DEFAULT_TAPE_NAMESPACE


@pytest.mark.asyncio
async def test_mimic_mode(backend_server_url, proxay_server_runner, fake_redis):
    """
    Tests that mimic mode records the first time and replays the second time.
    """
    proxay_port = 9003
    tape_name = "test_mimic"
    full_tape_name = f"{DEFAULT_TAPE_NAMESPACE}:{tape_name}"
    path = "/mimic-test"

    server = RecordReplayServer(
        initial_mode="mimic",
        default_tape_name=tape_name,
        host=backend_server_url,
        redis_client=fake_redis,
    )
    proxay_url = proxay_server_runner(server, proxay_port)

    # First request should be recorded
    first_response = requests.get(f"{proxay_url}{path}")
    assert first_response.status_code == 200
    assert "x-original-path" in first_response.headers
    assert first_response.headers["x-original-path"] == path

    tape_yaml_before = fake_redis.get(full_tape_name)
    interactions_before = yaml.safe_load(tape_yaml_before)["http_interactions"]
    assert len(interactions_before) == 1

    # Second request should be replayed
    second_response = requests.get(f"{proxay_url}{path}")
    assert second_response.status_code == 200
    assert second_response.headers["x-original-path"] == path

    tape_yaml_after = fake_redis.get(full_tape_name)
    interactions_after = yaml.safe_load(tape_yaml_after)["http_interactions"]
    assert len(interactions_after) == len(interactions_before)

    # A different request should be recorded
    requests.get(f"{proxay_url}{path}?param=2")
    tape_yaml_final = fake_redis.get(full_tape_name)
    interactions_final = yaml.safe_load(tape_yaml_final)["http_interactions"]
    assert len(interactions_final) == 2

    # And now replayed
    requests.get(f"{proxay_url}{path}?param=2")
    tape_yaml_final_replay = fake_redis.get(full_tape_name)
    interactions_final_replay = yaml.safe_load(tape_yaml_final_replay)["http_interactions"]
    assert len(interactions_final_replay) == 2
