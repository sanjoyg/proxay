from dataclasses import dataclass
from typing import TypedDict, Optional

from .compression import CompressionAlgorithm
from .http import HttpHeaders, HttpRequest, HttpResponse

# In-memory representation
@dataclass
class TapeRecord:
    request: HttpRequest
    response: HttpResponse

# On-disk representation (what gets serialized to/from YAML and stored in Redis)
# Using TypedDict as it maps directly to the structure of the loaded YAML.

class PersistedBuffer(TypedDict):
    encoding: str  # "base64" or "utf8"
    data: str
    compression: Optional[CompressionAlgorithm]

class PersistedHttpStatus(TypedDict):
    code: int

class PersistedRequest(TypedDict):
    method: str
    path: str
    headers: HttpHeaders
    body: PersistedBuffer

class PersistedResponse(TypedDict):
    status: PersistedHttpStatus
    headers: HttpHeaders
    body: PersistedBuffer

class PersistedTapeRecord(TypedDict):
    request: PersistedRequest
    response: PersistedResponse
