import base64
from typing import List, Union

import redis
import yaml

from .http import HttpRequest, HttpResponse, HttpStatus
from .tape import (
    PersistedBuffer,
    PersistedHttpStatus,
    PersistedRequest,
    PersistedResponse,
    PersistedTapeRecord,
    TapeRecord,
)


class Persistence:
    def __init__(self, redis_client: redis.Redis, redact_headers: List[str]):
        self.redis = redis_client
        self.redact_headers = redact_headers

    def save_tape(self, tape_name: str, tape_records: List[TapeRecord]):
        persisted_tape_records = [
            self._persist_tape_record(self._redact(record)) for record in tape_records
        ]
        tape_data = {"http_interactions": persisted_tape_records}
        yaml_data = yaml.safe_dump(tape_data)
        self.redis.set(tape_name, yaml_data)

    def load_tape(self, tape_name: str) -> List[TapeRecord]:
        yaml_data = self.redis.get(tape_name)
        if yaml_data is None:
            raise FileNotFoundError(f"No tape found with name {tape_name}")

        tape_data = yaml.safe_load(yaml_data)
        persisted_tape_records = tape_data.get("http_interactions", [])
        return [self._revive_tape_record(record) for record in persisted_tape_records]

    def is_tape_name_valid(self, tape_name: str) -> bool:
        # This check is for the short name provided via the API
        return "/" not in tape_name and "\\" not in tape_name

    def _redact(self, record: TapeRecord) -> TapeRecord:
        headers_lower = {h.lower() for h in self.redact_headers}
        redacted_headers = record.request.headers.copy()
        for key in record.request.headers:
            if key.lower() in headers_lower:
                redacted_headers[key] = "XXXX"
        record.request.headers = redacted_headers
        return record

    def _persist_tape_record(self, record: TapeRecord) -> PersistedTapeRecord:
        return PersistedTapeRecord(
            request=PersistedRequest(
                method=record.request.method,
                path=record.request.path,
                headers=record.request.headers,
                body=self._serialize_body(record.request),
            ),
            response=PersistedResponse(
                status=PersistedHttpStatus(code=record.response.status.code),
                headers=record.response.headers,
                body=self._serialize_body(record.response),
            ),
        )

    def _revive_tape_record(
        self, persisted_record: PersistedTapeRecord
    ) -> TapeRecord:
        return TapeRecord(
            request=HttpRequest(
                method=persisted_record["request"]["method"],
                path=persisted_record["request"]["path"],
                headers=persisted_record["request"]["headers"],
                body=self._unserialize_buffer(persisted_record["request"]["body"]),
            ),
            response=HttpResponse(
                status=HttpStatus(code=persisted_record["response"]["status"]["code"]),
                headers=persisted_record["response"]["headers"],
                body=self._unserialize_buffer(persisted_record["response"]["body"]),
            ),
        )

    def _serialize_body(self, r: Union[HttpRequest, HttpResponse]) -> PersistedBuffer:
        # Using simple, robust base64 encoding for the body. No compression.
        return PersistedBuffer(
            encoding="base64",
            data=base64.b64encode(r.body).decode("ascii"),
            compression=None,
        )

    def _unserialize_buffer(self, persisted: PersistedBuffer) -> bytes:
        return base64.b64decode(persisted.get("data"))
