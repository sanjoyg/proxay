import pytest
import requests

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

    # 1. Setup Proxay in mimic mode with an empty tape
    server = RecordReplayServer(
        initial_mode="mimic",
        default_tape_name=tape_name,
        host=backend_server_url,
        redis_client=fake_redis,
    )
    proxay_url = proxay_server_runner(server, proxay_port)

    # 2. Make the first request - this should be recorded
    first_response = requests.get(f"{proxay_url}{path}")
    assert first_response.status_code == 200
    assert "x-original-path" in first_response.headers
    assert first_response.headers["x-original-path"] == path

    # 3. Make the second request - this should be replayed
    tape_records_before = fake_redis.llen(full_tape_name)
    assert tape_records_before == 1

    second_response = requests.get(f"{proxay_url}{path}")
    assert second_response.status_code == 200
    assert second_response.headers["x-original-path"] == path

    tape_records_after = fake_redis.llen(full_tape_name)
    assert tape_records_after == tape_records_before

    # 4. A different request should be recorded
    third_response = requests.get(f"{proxay_url}{path}?param=2")
    assert third_response.status_code == 200

    tape_records_final = fake_redis.llen(full_tape_name)
    assert tape_records_final == 2

    # And now replayed
    fourth_response = requests.get(f"{proxay_url}{path}?param=2")
    assert fourth_response.status_code == 200
    assert fake_redis.llen(full_tape_name) == 2
