import asyncio
from contextlib import asynccontextmanager
from typing import List, Optional

import redis
import uvicorn
from fastapi import FastAPI, Request, Response
from termcolor import cprint

from .http import HttpRequest, HttpResponse
from .matcher import find_next_record_to_replay, find_record_matches
from .modes import Mode
from .persistence import Persistence
from .rewrite import RewriteRules
from .sender import send
from proxay import stats
from .tape import TapeRecord

DEFAULT_TAPE_NAMESPACE = "proxay"


class RecordReplayServer:
    def __init__(
        self,
        initial_mode: Mode,
        default_tape_name: str,
        host: Optional[str],
        redis_host: str = "localhost",
        redis_port: int = 6379,
        redis_client: Optional[redis.Redis] = None,
        proxy_port_to_send: Optional[int] = None,
        timeout: int = 5000,
        enable_logging: bool = False,
        redact_headers: Optional[List[str]] = None,
        prevent_conditional_requests: bool = False,
        rewrite_before_diff_rules: Optional[RewriteRules] = None,
        ignore_headers: Optional[List[str]] = None,
        exact_request_matching: bool = False,
        debug_matcher_fails: bool = False,
    ):
        self.mode = initial_mode
        self.tape_namespace = DEFAULT_TAPE_NAMESPACE
        self.proxied_host = host
        self.proxy_port_to_send = proxy_port_to_send
        self.timeout = timeout
        self.verbose = enable_logging
        self.redact_headers = redact_headers or []

        if redis_client:
            self.redis_client = redis_client
        else:
            self.redis_client = redis.Redis(host=redis_host, port=redis_port, db=0)

        self.persistence = Persistence(self.redis_client, self.redact_headers)

        self.default_tape = self._get_full_tape_name(default_tape_name)
        self.prevent_conditional_requests = prevent_conditional_requests
        self.rewrite_before_diff_rules = rewrite_before_diff_rules or RewriteRules()
        self.ignore_headers = ignore_headers or []
        self.exact_request_matching = exact_request_matching
        self.debug_matcher_fails = debug_matcher_fails

        self.current_tape_records: List[TapeRecord] = []
        self.current_tape: str = ""
        self.replayed_tapes: List[TapeRecord] = []

        self.stats_collector = stats.MimicStatsCollector(verbose=self.verbose)
        self.reporter_task: Optional[asyncio.Task] = None
        self.shutdown_event = asyncio.Event()

        self.load_tape(self.default_tape)

        self.app = FastAPI(lifespan=self.lifespan)
        self.setup_routes()

    @asynccontextmanager
    async def lifespan(self, app: FastAPI):
        if self.mode == "mimic" and self.verbose:
            self.shutdown_event.clear()
            self.reporter_task = asyncio.create_task(
                stats.periodic_reporter(self.stats_collector, self.shutdown_event)
            )
        yield
        if self.reporter_task:
            self.shutdown_event.set()
            try:
                await asyncio.wait_for(self.reporter_task, timeout=1.0)
            except asyncio.TimeoutError:
                self.reporter_task.cancel()


    def _get_full_tape_name(self, tape_name: str) -> str:
        return f"{self.tape_namespace}:{tape_name}"

    def setup_routes(self):
        @self.app.get("/__proxay")
        async def proxay_api_get():
            return Response(content="Proxay!", status_code=200)

        @self.app.post("/__proxay/tape")
        async def proxay_api_post_tape(request: Request):
            body = await request.json()
            tape_name = body.get("tape")
            new_mode = body.get("mode")

            if new_mode and new_mode != self.mode:
                self.mode = new_mode
                cprint(f"Switched to mode: {self.mode}", "blue")

            if tape_name:
                full_tape_name = self._get_full_tape_name(tape_name)
                if not self.persistence.is_tape_name_valid(tape_name):
                    return Response(f"Invalid tape name: {tape_name}", status_code=403)
                if self.load_tape(full_tape_name):
                    return Response(f"Updated tape: {full_tape_name}", status_code=200)
                else:
                    return Response(f"Missing tape: {full_tape_name}", status_code=404)
            else:
                self.unload_tape()
                return Response("Unloaded tape", status_code=200)

        @self.app.api_route("/{full_path:path}", methods=["GET", "POST", "PUT", "DELETE", "PATCH", "HEAD", "OPTIONS"])
        async def handle_request(request: Request):
            path_with_query = request.url.path
            if request.url.query:
                path_with_query += "?" + request.url.query

            http_request = HttpRequest(
                method=request.method,
                path=path_with_query,
                headers={k: v for k, v in request.headers.items()},
                body=await request.body(),
            )

            self.rewrite_request(http_request)

            try:
                record = await self.fetch_response(http_request)
                if record:
                    return Response(
                        content=record.response.body,
                        status_code=record.response.status.code,
                        headers=record.response.headers,
                    )
                else:
                    return Response("No matching record found for replay.", status_code=500)
            except Exception as e:
                if self.verbose:
                    cprint(f"Unexpected error: {e}", "red")
                return Response("Internal Server Error", status_code=500)

    def rewrite_request(self, request: HttpRequest):
        if self.prevent_conditional_requests and request.method in ["GET", "HEAD"]:
            headers = request.headers.copy()
            headers.pop("if-modified-since", None)
            headers.pop("if-none-match", None)
            request.headers = headers

    async def fetch_response(self, request: HttpRequest) -> Optional[TapeRecord]:
        if self.mode == "replay":
            return await self.fetch_replay_response(request)
        if self.mode == "record":
            return await self.fetch_record_response(request)
        if self.mode == "mimic":
            return await self.fetch_mimic_response(request)
        if self.mode == "passthrough":
            return await self.fetch_passthrough_response(request)
        raise ValueError(f"Unknown mode: {self.mode}")

    async def fetch_record_response(self, request: HttpRequest) -> Optional[TapeRecord]:
        if not self.proxied_host:
            raise ValueError("Missing proxied host")
        record = send(request, self.proxied_host, self.timeout, self.proxy_port_to_send, self.verbose)
        self.add_record_to_tape(record)
        if self.verbose:
            print(f"Recorded: {request.method} {request.path}")
        return record

    async def fetch_replay_response(self, request: HttpRequest) -> Optional[TapeRecord]:
        matches = find_record_matches(
            request, self.current_tape_records, self.rewrite_before_diff_rules,
            self.exact_request_matching, self.debug_matcher_fails, self.ignore_headers
        )
        record = find_next_record_to_replay(matches, self.replayed_tapes)
        if record:
            self.replayed_tapes.append(record)
            if self.verbose:
                print(f"Replayed: {request.method} {request.path}")
        else:
            if self.verbose:
                cprint(f"Unexpected request {request.method} {request.path} has no matching record.", "yellow")
        return record

    async def fetch_mimic_response(self, request: HttpRequest) -> Optional[TapeRecord]:
        matches = find_record_matches(
            request, self.current_tape_records, self.rewrite_before_diff_rules,
            self.exact_request_matching, self.debug_matcher_fails, self.ignore_headers
        )
        record = find_next_record_to_replay(matches, self.replayed_tapes)
        if record:
            self.stats_collector.record_hit()
            self.replayed_tapes.append(record)
            if self.verbose:
                print(f"Replayed from mimic: {request.method} {request.path}")
            return record
        else:
            self.stats_collector.record_miss()
            if not self.proxied_host:
                raise ValueError("Missing proxied host for mimic mode")
            new_record = send(request, self.proxied_host, self.timeout, self.proxy_port_to_send, self.verbose)
            self.add_record_to_tape(new_record)
            if self.verbose:
                print(f"Recorded in mimic: {request.method} {request.path}")
            return new_record

    async def fetch_passthrough_response(self, request: HttpRequest) -> Optional[TapeRecord]:
        if not self.proxied_host:
            raise ValueError("Missing proxied host")
        record = send(request, self.proxied_host, self.timeout, self.proxy_port_to_send, self.verbose)
        if self.verbose:
            print(f"Proxied: {request.method} {request.path}")
        return record

    def load_tape(self, tape_name: str) -> bool:
        self.current_tape = tape_name
        self.replayed_tapes.clear()
        if self.verbose:
            cprint(f"Loaded tape: {tape_name}", "blue")

        if self.mode == "record":
            self.current_tape_records = []
            self.persistence.save_tape(self.current_tape, [])
            return True
        if self.mode in ["replay", "mimic"]:
            try:
                self.current_tape_records = self.persistence.load_tape(self.current_tape)
                return True
            except FileNotFoundError:
                if self.mode == "mimic":
                    self.current_tape_records = []
                    self.persistence.save_tape(self.current_tape, [])
                    return True
                if self.verbose:
                    cprint(f"Tape '{tape_name}' not found.", "yellow")
                return False
        return True

    def unload_tape(self):
        self.load_tape(self.default_tape)

    def add_record_to_tape(self, record: TapeRecord):
        self.current_tape_records.append(record)
        self.persistence.save_tape(self.current_tape, self.current_tape_records)

    def start(self, port: int, host: str = "0.0.0.0"):
        uvicorn.run(self.app, host=host, port=port)
