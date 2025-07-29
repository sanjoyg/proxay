from dataclasses import dataclass
from typing import Dict, List, Union

# In Node, headers can be string or string[].
# In Python's http.server, headers are a single string.
# The 'requests' library returns a case-insensitive dict of strings.
# To match the original, we'll allow for a list of strings.
HttpHeaders = Dict[str, Union[str, List[str]]]

@dataclass
class HttpRequest:
    method: str
    path: str
    headers: HttpHeaders
    body: bytes

@dataclass
class HttpStatus:
    code: int

@dataclass
class HttpResponse:
    status: HttpStatus
    headers: HttpHeaders
    body: bytes
