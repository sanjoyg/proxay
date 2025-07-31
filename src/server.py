import logging
from typing import Set

import httpx
from fastapi import FastAPI, Request, Response
from fastapi.responses import JSONResponse

from .matcher import find_record_matches, find_next_record_to_replay
from .models import HttpRequest, TapeRecord
from .persistence import RedisPersistence

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class RecordReplayServer:
    def __init__(
        self,
        persistence: RedisPersistence,
        initial_mode: str,
        proxied_host: str | None,
        default_tape_name: str,
        enable_logging: bool = True,
    ):
        self.persistence = persistence
        self.mode = initial_mode
        self.proxied_host = proxied_host
        self.default_tape_name = default_tape_name
        self.logging_enabled = enable_logging

        self.current_tape_name: str = ""
        self.current_tape_records: list[TapeRecord] = []
        self.replayed_records: list[TapeRecord] = []

        self.http_client = httpx.AsyncClient()

        self.load_tape(self.default_tape_name)

    def load_tape(self, tape_name: str) -> bool:
        """Loads a tape into memory."""
        if self.logging_enabled:
            logger.info(f"Loading tape: {tape_name}")

        self.current_tape_name = tape_name
        self.replayed_records = []

        if self.mode == "record":
            self.current_tape_records = []
            self.persistence.save_tape(self.current_tape_name, [])
            return True
        elif self.mode == "replay":
            try:
                self.current_tape_records = self.persistence.load_tape(self.current_tape_name)
                return True
            except FileNotFoundError:
                logger.warning(f"Tape not found: {self.current_tape_name}")
                self.current_tape_records = []
                return False
        elif self.mode == "mimic":
            try:
                self.current_tape_records = self.persistence.load_tape(self.current_tape_name)
            except FileNotFoundError:
                self.current_tape_records = []
                self.persistence.save_tape(self.current_tape_name, [])
            return True
        elif self.mode == "passthrough":
            return True

        return False

    def unload_tape(self):
        """Unloads the current tape and falls back to the default."""
        self.load_tape(self.default_tape_name)

    def add_record_to_tape(self, record: TapeRecord):
        """Adds a new record to the tape and saves it."""
        self.current_tape_records.append(record)
        self.persistence.save_tape(self.current_tape_name, self.current_tape_records)

    async def fetch_response(self, request: HttpRequest) -> TapeRecord | None:
        """Fetches a response based on the current mode."""
        if self.mode == "record":
            return await self._fetch_record_response(request)
        elif self.mode == "replay":
            return await self._fetch_replay_response(request)
        elif self.mode == "mimic":
            return await self._fetch_mimic_response(request)
        elif self.mode == "passthrough":
            return await self._fetch_passthrough_response(request)
        return None

    async def _fetch_record_response(self, request: HttpRequest) -> TapeRecord | None:
        """Records a request by proxying it to the host."""
        if not self.proxied_host:
            logger.error("Cannot record without a proxied host.")
            return None

        record = await self._send_request(request)
        self.add_record_to_tape(record)
        if self.logging_enabled:
            logger.info(f"Recorded: {request.method} {request.path}")
        return record

    async def _fetch_replay_response(self, request: HttpRequest) -> TapeRecord | None:
        """Replays a response from the loaded tape."""
        matches = find_record_matches(request, self.current_tape_records)
        record = find_next_record_to_replay(matches, self.replayed_records)

        if record:
            self.replayed_records.append(record)
            if self.logging_enabled:
                logger.info(f"Replayed: {request.method} {request.path}")
        else:
            logger.warning(f"Unexpected request, no matching record found: {request.method} {request.path}")

        return record

    async def _fetch_mimic_response(self, request: HttpRequest) -> TapeRecord | None:
        """Tries to replay a response, otherwise records it."""
        matches = find_record_matches(request, self.current_tape_records)
        record = find_next_record_to_replay(matches, self.replayed_records)

        if record:
            self.replayed_records.append(record)
            if self.logging_enabled:
                logger.info(f"Replayed: {request.method} {request.path}")
            return record
        else:
            return await self._fetch_record_response(request)

    async def _fetch_passthrough_response(self, request: HttpRequest) -> TapeRecord | None:
        """Proxies a request without recording it."""
        if not self.proxied_host:
            logger.error("Cannot passthrough without a proxied host.")
            return None

        if self.logging_enabled:
            logger.info(f"Proxied: {request.method} {request.path}")
        return await self._send_request(request)

    async def _send_request(self, request: HttpRequest) -> TapeRecord:
        """Sends the request to the proxied host."""
        url = f"{self.proxied_host}{request.path}"

        # httpx needs headers as a dict of strings
        headers = {k: v if isinstance(v, str) else ','.join(v) for k, v in request.headers.items() if k.lower() not in ['host']}

        if self.logging_enabled:
            logger.info("--- Proxying request to backend ---")
            logger.info(f"Method: {request.method}")
            logger.info(f"URL: {url}")
            logger.info(f"Headers: {headers}")
            # Only log body if it's not too large to avoid spamming logs
            if len(request.body) < 1024:
                logger.info(f"Body: {request.body.decode('utf-8', 'ignore')}")
            else:
                logger.info(f"Body: (Omitted, size: {len(request.body)} bytes)")
            logger.info("------------------------------------")


        proxied_response = await self.http_client.request(
            method=request.method,
            url=url,
            headers=headers,
            content=request.body,
            timeout=10.0,
        )

        # httpx automatically handles content-encoding, so the body is decompressed.
        # We must remove the content-encoding header from the response we send
        # to the client, as we are not sending a compressed body.
        final_headers = {k.lower(): v for k, v in proxied_response.headers.items()}
        final_headers.pop("content-encoding", None)
        final_headers.pop("transfer-encoding", None)

        response_tape = TapeRecord(
            request=request,
            response={
                "status": {"code": proxied_response.status_code},
                "headers": final_headers,
                "body": proxied_response.content,
            },
        )
        return response_tape


# This will be configured and created by the CLI
app = FastAPI()
server: RecordReplayServer | None = None

@app.post("/__proxay/tape")
async def set_tape(request: Request):
    global server
    if not server:
        return JSONResponse({"error": "Server not initialized"}, status_code=500)

    try:
        body = await request.json()
        tape_name = body.get("tape")
        new_mode = body.get("mode")

        if new_mode and new_mode != server.mode:
            server.mode = new_mode
            if server.logging_enabled:
                logger.info(f"Switched mode to: {new_mode}")

        if tape_name:
            if not server.persistence.is_tape_name_valid(tape_name):
                return JSONResponse({"error": f"Invalid tape name: {tape_name}"}, status_code=400)

            if server.load_tape(tape_name):
                return {"message": f"Updated tape: {tape_name}"}
            else:
                return JSONResponse({"error": f"Missing tape: {tape_name}"}, status_code=404)

        return {"message": "Tape and/or mode updated."}

    except Exception as e:
        logger.error(f"Error handling /__proxay/tape: {e}")
        return JSONResponse({"error": "Invalid request body"}, status_code=400)


@app.get("/__proxay")
def health_check():
    return "Proxay!"


@app.api_route("/{full_path:path}", methods=["GET", "POST", "PUT", "DELETE", "PATCH", "HEAD", "OPTIONS"])
async def handle_request(request: Request, full_path: str):
    logger.info(f"--- Handling request: {request.method} {request.url.path} ---")
    global server
    if not server:
        return Response("Proxay server not initialized.", status_code=503)

    # Reconstruct the path with query params
    path = f"/{full_path}"
    if request.query_params:
        path += f"?{request.query_params}"

    http_request = HttpRequest(
        method=request.method,
        path=path,
        headers=dict(request.headers),
        body=await request.body(),
    )

    record = await server.fetch_response(http_request)

    if record:
        return Response(
            content=record.response.body,
            status_code=record.response.status.code,
            headers=record.response.headers,
        )

    return Response(f"No matching record found for {http_request.method} {http_request.path}", status_code=404)
