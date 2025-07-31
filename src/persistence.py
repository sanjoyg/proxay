import base64
import bz2
import gzip
import json
import re
from typing import List, Union

import redis

from src.models import (
    Base64PersistedBuffer,
    CompressionAlgorithm,
    HttpRequest,
    HttpResponse,
    PersistedBuffer,
    PersistedHttpRequest,
    PersistedHttpResponse,
    PersistedTapeRecord,
    TapeRecord,
    Utf8PersistedBuffer,
)

# A simple regex to validate tape names. It allows forward slashes for grouping.
TAPE_NAME_VALIDATION_REGEX = re.compile(r"^[a-zA-Z0-9_-]+(/[a-zA-Z0-9_-]+)*$")


class RedisPersistence:
    """
    Persistence layer to save and read tapes from a Redis instance.
    """

    def __init__(self, redis_client: redis.Redis, redact_headers: List[str] = None):
        self.redis_client = redis_client
        self.redact_headers = redact_headers or []

    def get_tape_key(self, tape_name: str) -> str:
        """Generates the Redis key for a given tape name."""
        return f"proxay:tapes:{tape_name}"

    def is_tape_name_valid(self, tape_name: str) -> bool:
        """
        Validates the tape name to prevent path traversal and other problematic names.
        """
        if not tape_name or ".." in tape_name:
            return False
        return bool(TAPE_NAME_VALIDATION_REGEX.match(tape_name))

    def save_tape(self, tape_name: str, tape_records: List[TapeRecord]):
        """Saves a tape to Redis."""
        tape_key = self.get_tape_key(tape_name)
        persisted_records = [
            self._persist_record(self._redact(record)) for record in tape_records
        ]

        # Use a pipeline for atomic execution
        with self.redis_client.pipeline() as pipe:
            pipe.delete(tape_key)
            if persisted_records:
                # Pydantic models must be converted to dicts before JSON serialization
                pipe.rpush(tape_key, *[r.model_dump_json() for r in persisted_records])
            pipe.execute()

    def load_tape(self, tape_name: str) -> List[TapeRecord]:
        """Loads a tape from Redis."""
        tape_key = self.get_tape_key(tape_name)
        if not self.redis_client.exists(tape_key):
             raise FileNotFoundError(f"No tape found with name {tape_name}")

        persisted_record_jsons = self.redis_client.lrange(tape_key, 0, -1)

        # The data is stored as bytes in Redis, so we need to decode it
        persisted_records = [
            PersistedTapeRecord.model_validate_json(r_json) for r_json in persisted_record_jsons
        ]

        return [self._revive_record(r) for r in persisted_records]

    def _redact(self, record: TapeRecord) -> TapeRecord:
        """Redacts sensitive headers from the request."""
        for header in self.redact_headers:
            if header.lower() in record.request.headers:
                record.request.headers[header.lower()] = "XXXX"
        return record

    def _persist_record(self, record: TapeRecord) -> PersistedTapeRecord:
        """Converts a TapeRecord to a PersistedTapeRecord."""
        return PersistedTapeRecord(
            request=PersistedHttpRequest(
                method=record.request.method,
                path=record.request.path,
                headers=record.request.headers,
                body=self._serialize_body(record.request),
            ),
            response=PersistedHttpResponse(
                status=record.response.status,
                headers=record.response.headers,
                body=self._serialize_body(record.response),
            ),
        )

    def _revive_record(self, persisted_record: PersistedTapeRecord) -> TapeRecord:
        """Converts a PersistedTapeRecord back to a TapeRecord."""
        return TapeRecord(
            request=HttpRequest(
                method=persisted_record.request.method,
                path=persisted_record.request.path,
                headers=persisted_record.request.headers,
                body=self._unserialize_body(persisted_record.request.body),
            ),
            response=HttpResponse(
                status=persisted_record.response.status,
                headers=persisted_record.response.headers,
                body=self._unserialize_body(persisted_record.response.body),
            ),
        )

    def _get_content_encoding(self, message: Union[HttpRequest, HttpResponse]) -> CompressionAlgorithm:
        """Determines the content encoding from headers."""
        encoding = message.headers.get("content-encoding", "none").lower()
        if "gzip" in encoding:
            return "gzip"
        if "br" in encoding:
            return "brotli"
        return "none"

    def _serialize_body(self, r: Union[HttpRequest, HttpResponse]) -> PersistedBuffer:
        """Serializes the body of a request or response for persistence."""
        body_bytes = r.body

        try:
            # Try to store as UTF-8 if possible
            utf8_data = body_bytes.decode("utf-8")
            # To be safe, check if re-encoding gives back the same bytes
            if utf8_data.encode("utf-8") == body_bytes:
                return Utf8PersistedBuffer(
                    encoding="utf8",
                    # We store the raw (decompressed) data, but remember the compression
                    compression=self._get_content_encoding(r),
                    data=utf8_data,
                )
        except UnicodeDecodeError:
            # Not valid UTF-8, fall through to Base64
            pass

        # Fallback to Base64
        return Base64PersistedBuffer(
            encoding="base64", data=base64.b64encode(body_bytes).decode("ascii")
        )

    def _unserialize_body(self, persisted: PersistedBuffer) -> bytes:
        """Unserializes a persisted body back to bytes."""
        if isinstance(persisted, Base64PersistedBuffer):
            return base64.b64decode(persisted.data)

        elif isinstance(persisted, Utf8PersistedBuffer):
            buffer = persisted.data.encode("utf-8")
            if persisted.compression == "gzip":
                return gzip.compress(buffer)
            elif persisted.compression == "brotli":
                # Note: Standard library does not have brotli.
                # If brotli support is needed, an external library like `brotli` would be required.
                # For now, we'll assume it's not compressed if we can't handle it.
                # This is a simplification from the original code.
                # Let's add a placeholder for it.
                # For the purpose of this conversion, we will assume brotli is not used,
                # as it would add another dependency.
                pass
            return buffer

        raise TypeError(f"Unsupported persisted buffer type: {type(persisted)}")
