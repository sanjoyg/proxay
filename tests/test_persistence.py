import pytest
import fakeredis

from src.models import HttpRequest, HttpResponse, TapeRecord
from src.persistence import RedisPersistence

@pytest.fixture
def fake_redis_client():
    """Provides a fake redis client for tests."""
    # The `decode_responses=True` is important, as our code expects it.
    return fakeredis.FakeRedis(decode_responses=True)

@pytest.fixture
def persistence(fake_redis_client):
    """Provides a RedisPersistence instance initialized with the fake client."""
    return RedisPersistence(redis_client=fake_redis_client)

@pytest.fixture
def sample_tape_record():
    """A sample TapeRecord for use in tests."""
    return TapeRecord(
        request=HttpRequest(
            method="GET",
            path="/test",
            headers={"accept": "application/json"},
            body=b'{"key": "value"}',
        ),
        response=HttpResponse(
            status={"code": 200},
            headers={"content-type": "application/json"},
            body=b'{"ok": true}',
        ),
    )

def test_is_tape_name_valid(persistence: RedisPersistence):
    assert persistence.is_tape_name_valid("my-tape")
    assert persistence.is_tape_name_valid("group/my-tape")
    assert not persistence.is_tape_name_valid("../invalid")
    assert not persistence.is_tape_name_valid("invalid-name?")
    assert not persistence.is_tape_name_valid("")

def test_save_and_load_tape(persistence: RedisPersistence, sample_tape_record: TapeRecord):
    tape_name = "test-tape"
    records_to_save = [sample_tape_record]

    # Save the tape
    persistence.save_tape(tape_name, records_to_save)

    # Load the tape
    loaded_records = persistence.load_tape(tape_name)

    assert len(loaded_records) == 1
    # Pydantic models are comparable
    assert loaded_records[0] == sample_tape_record

def test_save_empty_tape(persistence: RedisPersistence):
    tape_name = "empty-tape"
    # Saving an empty tape should result in the key being deleted.
    persistence.save_tape(tape_name, [])

    # The key should not exist in Redis.
    assert not persistence.redis_client.exists(persistence.get_tape_key(tape_name))

    # Therefore, loading it should raise a FileNotFoundError.
    with pytest.raises(FileNotFoundError):
        persistence.load_tape(tape_name)

def test_load_non_existent_tape(persistence: RedisPersistence):
    with pytest.raises(FileNotFoundError):
        persistence.load_tape("non-existent-tape")

def test_redact_headers(persistence: RedisPersistence, sample_tape_record: TapeRecord):
    persistence.redact_headers = ["accept"]
    tape_name = "redacted-tape"

    persistence.save_tape(tape_name, [sample_tape_record])

    # Use the raw redis client to inspect the saved data
    tape_key = persistence.get_tape_key(tape_name)
    saved_json = persistence.redis_client.lrange(tape_key, 0, -1)[0]

    import json
    saved_data = json.loads(saved_json)

    # The header should be redacted in the saved data
    assert saved_data["request"]["headers"]["accept"] == "XXXX"

    # The loaded record should also have the redacted header
    loaded_records = persistence.load_tape(tape_name)
    assert loaded_records[0].request.headers["accept"] == "XXXX"

def test_body_serialization(persistence: RedisPersistence):
    # Test UTF-8 text body
    text_record = TapeRecord(
        request=HttpRequest(method="POST", path="/text", headers={}, body="Hello, World!".encode("utf-8")),
        response=HttpResponse(status={"code": 200}, headers={}, body=b"OK"),
    )
    # Test binary (image) body
    binary_body = b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR..." # Fake image data
    binary_record = TapeRecord(
        request=HttpRequest(method="POST", path="/image", headers={}, body=binary_body),
        response=HttpResponse(status={"code": 200}, headers={}, body=b"OK"),
    )

    persistence.save_tape("body-test-tape", [text_record, binary_record])
    loaded_records = persistence.load_tape("body-test-tape")

    assert len(loaded_records) == 2
    assert loaded_records[0].request.body == text_record.request.body
    assert loaded_records[1].request.body == binary_record.request.body
