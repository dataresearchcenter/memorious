"""WARC record assembly for archived HTTP responses.
Generates a warc-format response and request record (one each) from the streamed
body file and the http response/request objects. This is not strictly 
'on the wire' data, as it uses the decoded/decompressed payload (that's why we drop
some http headers like Content-Encoding, Content-Length, otherwise replays break)
"""

from __future__ import annotations

import io
from pathlib import Path

import httpx
from warcio.statusandheaders import StatusAndHeaders
from warcio.warcwriter import WARCWriter


def build_warc(
    request: httpx.Request,
    response: httpx.Response,
    body_path: Path
) -> Path:
    """Assemble a response + linked request WARC as bytes.

    Args:
        request: the original httpx request
        response: the final (after redirect) response
        body_path: tmp path to the streamed payload
    Returns:
        Path to warc file
    """
    
    warc_path = body_path.parent / f"{body_path.stem}.warc"


    with open(warc_path, 'wb') as out:
        writer = WARCWriter(out, gzip=False)

        resp_headers = StatusAndHeaders(
            f"{response.status_code} {response.reason_phrase}",
            [(k, v) for k, v in response.headers.items()],
            protocol="HTTP/1.1",
        )
        with open(body_path, "rb") as payload:
            response_record = writer.create_warc_record(
                str(response.url),
                "response",
                payload=payload,
                http_headers=resp_headers,
            )
            writer.write_record(response_record)

        req_headers = StatusAndHeaders(
            f"{request.method} {request.url.raw_path.decode('ascii')} HTTP/1.1",
            [(k, v) for k, v in request.headers.items()],
            is_http_request=True,
        )
        request_record = writer.create_warc_record(
            str(request.url),
            "request",
            payload=io.BytesIO(request.content or b""),
            http_headers=req_headers,
            warc_content_type="application/http; msgtype=request",
        )
        request_record.rec_headers.add_header(
            "WARC-Concurrent-To",
            response_record.rec_headers.get_header("WARC-Record-ID"),
        )
        writer.write_record(request_record)

    return Path(warc_path)
