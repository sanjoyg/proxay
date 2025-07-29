import brotli
import zlib
from typing import Literal, Union

from .http import HttpRequest, HttpResponse

CompressionAlgorithm = Literal["gzip", "brotli", "none"]

def decompress_buffer(algorithm: CompressionAlgorithm, buffer: bytes) -> bytes:
    """Decompresses a buffer, handling potential errors gracefully."""
    if not buffer or algorithm == "none":
        return buffer

    try:
        if algorithm == "gzip":
            return zlib.decompress(buffer, wbits=16 + zlib.MAX_WBITS)
        elif algorithm == "brotli":
            return brotli.decompress(buffer)
    except (zlib.error, brotli.error):
        # If decompression fails, the Content-Encoding header was likely incorrect.
        return buffer

    return buffer

def compress_buffer(algorithm: CompressionAlgorithm, buffer: bytes) -> bytes:
    if algorithm == "gzip":
        return zlib.compress(buffer)
    elif algorithm == "brotli":
        return brotli.compress(buffer)
    return buffer

def get_http_content_encoding(r: Union[HttpRequest, HttpResponse]) -> str | None:
    for key, value in r.headers.items():
        if key.lower() == "content-encoding":
            if isinstance(value, list):
                return value[0] if value else None
            return value
    return None

def convert_http_content_encoding_to_compression_algorithm(encoding: str | None) -> CompressionAlgorithm:
    encoding_lower = (encoding or "").lower()
    if encoding_lower == "gzip":
        return "gzip"
    elif encoding_lower == "br":
        return "brotli"
    return "none"

def get_http_body_decoded(r: Union[HttpRequest, HttpResponse]) -> bytes:
    content_encoding = get_http_content_encoding(r)
    algorithm = convert_http_content_encoding_to_compression_algorithm(content_encoding)
    return decompress_buffer(algorithm, r.body)
