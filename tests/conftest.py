import threading
import time

import pytest
import uvicorn
from fakeredis import FakeRedis

from proxay.server import RecordReplayServer
from tests.test_backend_server import create_test_server


class UvicornTestServer(threading.Thread):
    def __init__(self, app, host="127.0.0.1", port=8081):
        super().__init__(daemon=True)
        self.config = uvicorn.Config(app, host=host, port=port)
        self.server = uvicorn.Server(self.config)
        self._startup_done = threading.Event()

    def run(self):
        self.server.run()

    def start(self):
        super().start()
        # Wait for the server to start by checking if the server has started
        while not self.server.started:
            time.sleep(0.01)

    def stop(self):
        self.server.should_exit = True
        self.join(timeout=1)


@pytest.fixture(scope="session")
def backend_server_url():
    """Starts the test backend server and yields its URL."""
    server = UvicornTestServer(create_test_server(), port=8081)
    server.start()
    yield "http://127.0.0.1:8081"
    server.stop()


@pytest.fixture
def proxay_server_runner():
    """A fixture that provides a function to run a Proxay server instance."""
    server_thread = None

    def _run_server(server: RecordReplayServer, port: int):
        nonlocal server_thread
        server_thread = UvicornTestServer(server.app, port=port)
        server_thread.start()
        return f"http://127.0.0.1:{port}"

    yield _run_server

    if server_thread:
        server_thread.stop()


@pytest.fixture
def fake_redis():
    """Provides a FakeRedis instance for tests, configured to decode responses."""
    return FakeRedis(decode_responses=True)
