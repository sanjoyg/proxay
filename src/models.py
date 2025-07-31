from typing import Any, Dict, List, Literal, Optional, Union

from pydantic import BaseModel, Field

# Represents the HTTP headers, which can have single or multiple values.
HttpHeaders = Dict[str, Union[str, List[str]]]

# Defines the available compression algorithms.
CompressionAlgorithm = Literal["gzip", "brotli", "none"]


class HttpRequest(BaseModel):
    """Represents an HTTP request."""
    method: str
    path: str
    headers: HttpHeaders
    body: bytes

    class Config:
        frozen = True


class Status(BaseModel):
    """Represents the status of an HTTP response."""
    code: int

    class Config:
        frozen = True


class HttpResponse(BaseModel):
    """Represents an HTTP response."""
    status: Status
    headers: HttpHeaders
    body: bytes

    class Config:
        frozen = True


class Base64PersistedBuffer(BaseModel):
    """Represents a buffer persisted in Base64 encoding."""
    encoding: Literal["base64"]
    data: str


class Utf8PersistedBuffer(BaseModel):
    """Represents a buffer persisted in UTF-8 encoding, with optional compression."""
    encoding: Literal["utf8"]
    compression: Optional[CompressionAlgorithm] = None
    data: str


# A union type to represent a buffer that can be persisted in different ways.
# The `encoding` field is used as a discriminator.
PersistedBuffer = Union[Base64PersistedBuffer, Utf8PersistedBuffer]


class PersistedHttpRequest(BaseModel):
    """The persisted representation of an HttpRequest."""
    method: str
    path: str
    headers: HttpHeaders
    body: PersistedBuffer


class PersistedHttpResponse(BaseModel):
    """The persisted representation of an HttpResponse."""
    status: Status
    headers: HttpHeaders
    body: PersistedBuffer


class TapeRecord(BaseModel):
    """A record of a single HTTP interaction (request and response)."""
    request: HttpRequest
    response: HttpResponse

    class Config:
        frozen = True


class PersistedTapeRecord(BaseModel):
    """The persisted version of a TapeRecord."""
    request: PersistedHttpRequest
    response: PersistedHttpResponse

    class Config:
        # Pydantic v2 needs this to handle discriminated unions correctly
        # when exporting to JSON.
        json_encoders = {
            PersistedBuffer: lambda v: v.model_dump()
        }
