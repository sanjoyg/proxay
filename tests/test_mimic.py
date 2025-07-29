import pytest
import requests

from proxay.server import RecordReplayServer


@pytest.mark.asyncio
async def test_mimic_mode(backend_server_url, proxay_server_runner, fake_redis):
    """
    Tests that mimic mode records the first time and replays the second time.
    """
    proxay_port = 9003
    tape_name = "test_mimic"
    path = "/mimic-test"

    # 1. Setup Proxay in mimic mode with an empty tape
    server = RecordReplayServer(
        initial_mode="mimic",
        tape_dir="tapes",
        default_tape_name=tape_name,
        host=backend_server_url,
        redis_client=fake_redis,
    )
    server.load_tape(tape_name)
    proxay_url = proxay_server_runner(server, proxay_port)

    # 2. Make the first request - this should be recorded
    first_response = requests.get(f"{proxay_url}{path}")
    assert first_response.status_code == 200
    # This header comes from the live backend, so it was recorded
    assert "x-original-path" in first_response.headers
    assert first_response.headers["x-original-path"] == path

    # 3. Make the second request - this should be replayed
    # To prove it's replayed, we can check that it works even if the backend is down.
    # But a simpler way is to check the logs or some other side effect.
    # The recorded response will have the 'x-original-path' header.
    # Let's check the redis tape count.

    tape_records_before = fake_redis.llen(tape_name)
    assert tape_records_before == 1

    second_response = requests.get(f"{proxay_url}{path}")
    assert second_response.status_code == 200
    assert second_response.headers["x-original-path"] == path

    # The number of records on the tape should NOT have changed.
    tape_records_after = fake_redis.llen(tape_name)
    assert tape_records_after == tape_records_before

    # 4. A different request should be recorded
    third_response = requests.get(f"{proxay_url}{path}?param=2")
    assert third_response.status_code == 200

    tape_records_final = fake_redis.llen(tape_name)
    assert tape_records_final == 2

    # And now replayed
    fourth_response = requests.get(f"{proxay_url}{path}?param=2")
    assert fourth_response.status_code == 200
    assert fake_redis.llen(tape_name) == 2
