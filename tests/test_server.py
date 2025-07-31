import pytest
import fakeredis
import httpx
from fastapi import FastAPI, Request
from fastapi.testclient import TestClient

# Import the server and persistence classes
from src import server as server_module
from src.persistence import RedisPersistence
from src.server import RecordReplayServer

# A simple backend API server to use as the target for proxying
backend_app = FastAPI()

@backend_app.get("/hello")
def read_hello():
    return {"message": "Hello, World!"}

@backend_app.post("/data")
async def create_data(request: Request):
    return {"received": await request.json()}

@pytest.fixture(scope="module")
def backend_client():
    """A client to interact with the backend server."""
    return TestClient(backend_app)

@pytest.fixture
def fake_redis_client():
    """Provides a fake redis client for tests."""
    return fakeredis.FakeRedis(decode_responses=True)

@pytest.fixture
def persistence(fake_redis_client):
    """Provides a RedisPersistence instance for tests."""
    return RedisPersistence(redis_client=fake_redis_client)


def create_test_proxay_client(
    persistence: RedisPersistence, mode: str, host: str, backend_app_instance: FastAPI
) -> TestClient:
    """Factory for creating a proxay TestClient in a specific mode."""
    server_instance = RecordReplayServer(
        persistence=persistence,
        initial_mode=mode,
        proxied_host=host,
        default_tape_name="test-tape",
        enable_logging=False,  # Disable logging for cleaner test output
    )

    # Configure the http_client to talk to the backend app directly
    server_instance.http_client = httpx.AsyncClient(
        transport=httpx.ASGITransport(app=backend_app_instance)
    )

    server_module.server = server_instance
    return TestClient(server_module.app)


def test_record_mode(persistence: RedisPersistence, backend_client: TestClient, backend_app_fixture: FastAPI):
    proxay_client = create_test_proxay_client(
        persistence, "record", str(backend_client.base_url), backend_app_fixture
    )

    # Make a request through proxay
    response = proxay_client.get("/hello")
    assert response.status_code == 200
    assert response.json() == {"message": "Hello, World!"}

    # Verify that the interaction was recorded
    tape = persistence.load_tape("test-tape")
    assert len(tape) == 1
    assert tape[0].request.path == "/hello"
    assert tape[0].response.status.code == 200
    assert tape[0].response.body == b'{"message":"Hello, World!"}'


def test_replay_mode(persistence: RedisPersistence, backend_client: TestClient, backend_app_fixture: FastAPI):
    # First, record a tape
    record_client = create_test_proxay_client(
        persistence, "record", str(backend_client.base_url), backend_app_fixture
    )
    record_client.get("/hello")

    # Now, create a new client in replay mode
    replay_client = create_test_proxay_client(
        persistence, "replay", "http://dummy-host.com", backend_app_fixture
    )

    # Make the same request. It should be replayed from the tape.
    response = replay_client.get("/hello")
    assert response.status_code == 200
    assert response.json() == {"message": "Hello, World!"}

    # Verify that an unknown request fails
    response = replay_client.get("/unknown")
    assert response.status_code == 404


def test_mimic_mode(persistence: RedisPersistence, backend_client: TestClient, backend_app_fixture: FastAPI):
    proxay_client = create_test_proxay_client(
        persistence, "mimic", str(backend_client.base_url), backend_app_fixture
    )

    # First request should be proxied and recorded
    response1 = proxay_client.get("/hello")
    assert response1.status_code == 200
    tape = persistence.load_tape("test-tape")
    assert len(tape) == 1

    # Second request should be replayed
    response2 = proxay_client.get("/hello")
    assert response2.status_code == 200
    # We can't easily prove it wasn't proxied without more invasive checks,
    # but the logic is tested. We can check that no new records were added.
    tape = persistence.load_tape("test-tape")
    assert len(tape) == 1


def test_passthrough_mode(persistence: RedisPersistence, backend_client: TestClient, backend_app_fixture: FastAPI):
    proxay_client = create_test_proxay_client(
        persistence, "passthrough", str(backend_client.base_url), backend_app_fixture
    )

    response = proxay_client.get("/hello")
    assert response.status_code == 200
    assert response.json() == {"message": "Hello, World!"}

    # Verify that nothing was recorded
    with pytest.raises(FileNotFoundError):
        persistence.load_tape("test-tape")


@pytest.fixture
def backend_app_fixture():
    """Yields the backend_app instance for use in tests."""
    yield backend_app

def test_proxay_api_set_tape(persistence: RedisPersistence, backend_client: TestClient, backend_app_fixture: FastAPI):
    # 1. Create a client in record mode
    record_client = create_test_proxay_client(
        persistence, "record", str(backend_client.base_url), backend_app_fixture
    )

    # 2. Use the API to switch to a new tape named 'api-test-tape'
    api_response = record_client.post("/__proxay/tape", json={"tape": "api-test-tape"})
    assert api_response.status_code == 200
    assert api_response.json() == {"message": "Updated tape: api-test-tape"}

    # 3. Record a request to this new tape
    response = record_client.get("/hello")
    assert response.status_code == 200

    # Verify it was recorded to the correct tape
    tape = persistence.load_tape("api-test-tape")
    assert len(tape) == 1
    assert tape[0].request.path == "/hello"

    # 4. Create a new client in replay mode
    replay_client = create_test_proxay_client(
        persistence, "replay", "http://dummy-host.com", backend_app_fixture
    )

    # Verify it can't access the resource initially
    response = replay_client.get("/hello")
    assert response.status_code == 404 # Default tape 'test-tape' is empty

    # 5. Switch the replay client to the tape we just recorded
    api_response = replay_client.post("/__proxay/tape", json={"tape": "api-test-tape"})
    assert api_response.status_code == 200

    # 6. Now, the request should be successfully replayed
    response = replay_client.get("/hello")
    assert response.status_code == 200
    assert response.json() == {"message": "Hello, World!"}
