from typing import Optional

import requests
from requests.structures import CaseInsensitiveDict

from .http import HttpRequest, HttpResponse, HttpStatus
from .tape import TapeRecord


def send(
    request: HttpRequest,
    host: str,
    timeout: int,
    proxy_port_to_send: Optional[int] = None,
    logging_enabled: bool = False,
) -> TapeRecord:
    url = f"{host.rstrip('/')}{request.path}"

    # The original code filters some headers. `requests` handles many of these,
    # but we will be explicit for 'host' and 'content-length'.
    headers_to_send = CaseInsensitiveDict(request.headers)
    if "host" in headers_to_send:
        del headers_to_send["host"]
    if "content-length" in headers_to_send:
        del headers_to_send["content-length"]

    if proxy_port_to_send:
        from urllib.parse import urlparse

        parsed_host = urlparse(host)
        headers_to_send["Host"] = f"{parsed_host.hostname}:{proxy_port_to_send}"

    try:
        response = requests.request(
            method=request.method,
            url=url,
            headers=headers_to_send,
            data=request.body,
            timeout=timeout / 1000,  # requests uses seconds
            allow_redirects=False,
            verify=False,  # To mimic original behavior of allowing self-signed certs
        )

        response_headers = {k: v for k, v in response.headers.items()}

        http_response = HttpResponse(
            status=HttpStatus(code=response.status_code),
            headers=response_headers,
            body=response.content,
        )

        return TapeRecord(request=request, response=http_response)

    except requests.exceptions.RequestException as e:
        if logging_enabled:
            print(f"Error sending request to {url}: {e}")
        # Create a synthetic 500 error response
        error_response = HttpResponse(
            status=HttpStatus(code=500),
            headers={"Content-Type": "text/plain"},
            body=str(e).encode("utf-8"),
        )
        return TapeRecord(request=request, response=error_response)
