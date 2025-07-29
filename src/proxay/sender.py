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
            timeout=timeout / 1000,
            allow_redirects=False,
            verify=False,
        )

        # The `requests` library automatically decompresses the response body.
        # We must remove the content-encoding header to prevent our code from
        # trying to decompress it again. We also remove content-length
        # as it will be incorrect for the decompressed body.
        response_headers = CaseInsensitiveDict(response.headers)
        if "content-encoding" in response_headers:
            del response_headers["content-encoding"]
        if "content-length" in response_headers:
            del response_headers["content-length"]

        # Convert back to a standard dict for serialization
        final_headers = dict(response_headers)

        http_response = HttpResponse(
            status=HttpStatus(code=response.status_code),
            headers=final_headers,
            body=response.content,
        )

        return TapeRecord(request=request, response=http_response)

    except requests.exceptions.RequestException as e:
        if logging_enabled:
            print(f"Error sending request to {url}: {e}")
        error_response = HttpResponse(
            status=HttpStatus(code=502),
            headers={"Content-Type": "text/plain"},
            body=f"Error connecting to proxied host: {e}".encode("utf-8"),
        )
        return TapeRecord(request=request, response=error_response)
