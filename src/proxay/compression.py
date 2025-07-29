import brotli
import zlib
from typing import Literal, Union

from .http import HttpRequest, HttpResponse

CompressionAlgorithm = Literal["gzip", "brotli", "none"]

def decompress_buffer(algorithm: CompressionAlgorithm, buffer: bytes) -> bytes:
    if algorithm == "gzip":
        # The wbits parameter with 32 enables automatic detection of gzip or zlib headers.
        return zlib.decompress(buffer, wbits=16+zlib.MAX_WBITS)
    elif algorithm == "brotli":
        return brotli.decompress(buffer)
    # "none" or other cases
    return buffer

def compress_buffer(algorithm: CompressionAlgorithm, buffer: bytes) -> bytes:
    if algorithm == "gzip":
        return zlib.compress(buffer)
    elif algorithm == "brotli":
        return brotli.compress(buffer)
    # "none" or other cases
    return buffer

def get_http_content_encoding(r: Union[HttpRequest, HttpResponse]) -> str | None:
    # Headers are case-insensitive
    for key, value in r.headers.items():
        if key.lower() == "content-encoding":
            # In http.server, headers are a single string.
            # In 'requests', it's a string.
            # My HttpHeaders type hint allows for list, so I'll handle it.
            if isinstance(value, list):
                return value[0] if value else None
            return value
    return None

def convert_http_content_encoding_to_compression_algorithm(encoding: str | None) -> CompressionAlgorithm:
    if encoding == "gzip":
        return "gzip"
    elif encoding == "br":
        return "brotli"
    return "none"

def get_http_body_decoded(r: Union[HttpRequest, HttpResponse]) -> bytes:
    content_encoding = get_http_content_encoding(r)
    algorithm = convert_http_content_encoding_to_compression_algorithm(content_encoding)
    return decompress_buffer(algorithm, r.body)
