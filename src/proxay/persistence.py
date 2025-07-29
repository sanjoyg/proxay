import base64
from typing import List, Union

import msgpack
import redis

from .compression import (
    compress_buffer,
    convert_http_content_encoding_to_compression_algorithm,
    get_http_body_decoded,
    get_http_content_encoding,
)
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

        # Use a pipeline for atomic and efficient storage
        pipe = self.redis.pipeline()
        pipe.delete(tape_name)
        if persisted_tape_records:
            # Serialize each record with MessagePack and add to the list
            pipe.rpush(tape_name, *[msgpack.packb(record) for record in persisted_tape_records])
        pipe.execute()

    def load_tape(self, tape_name: str) -> List[TapeRecord]:
        # LRANGE returns a list of bytes
        persisted_data = self.redis.lrange(tape_name, 0, -1)
        if not persisted_data:
            # To match original behavior, raise FileNotFoundError for replay/mimic modes
            raise FileNotFoundError(f"No tape found with name {tape_name}")

        return [self._revive_tape_record(msgpack.unpackb(record)) for record in persisted_data]

    def is_tape_name_valid(self, tape_name: str) -> bool:
        return ".." not in tape_name and "/" not in tape_name and "\\" not in tape_name

    def _redact(self, record: TapeRecord) -> TapeRecord:
        headers_lower = {h.lower() for h in self.redact_headers}
        redacted_headers = record.request.headers.copy()
        for key in record.request.headers:
            if key.lower() in headers_lower:
                redacted_headers[key] = "XXXX"
        record.request.headers = redacted_headers
        return record

    def _persist_tape_record(self, record: TapeRecord) -> PersistedTapeRecord:
        # Convert dataclasses to dicts for serialization
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
        buffer = get_http_body_decoded(r)
        content_encoding = get_http_content_encoding(r)
        compression_algorithm = (
            convert_http_content_encoding_to_compression_algorithm(content_encoding)
        )

        # With MessagePack, we can just store bytes, but to keep the structure
        # similar to the original (which had to be YAML-safe), we can still
        # try to encode as UTF-8 for readability if desired.
        # However, for performance, let's just use base64 for the body.
        # This simplifies logic and is very robust.
        return PersistedBuffer(
            encoding="base64",
            data=base64.b64encode(r.body).decode("ascii"),
            compression=None,
        )

    def _unserialize_buffer(self, persisted: PersistedBuffer) -> bytes:
        # Since we now always serialize to base64, this is simpler.
        encoding = persisted.get("encoding")
        if encoding == "base64":
            return base64.b64decode(persisted.get("data"))
        else:
            # Kept for potential future extension, but current code won't produce this.
            raise ValueError(f"Unsupported encoding in persisted body: {encoding}")
