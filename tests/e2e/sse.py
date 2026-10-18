"""Reads an SSE response straight from the ASGI app, frame by frame.

`httpx.ASGITransport` buffers the whole body, so it cannot read a stream that stays open.
"""

import asyncio
from collections.abc import Callable, Mapping
from dataclasses import dataclass

from starlette.types import ASGIApp, Message

READ_TIMEOUT_SECONDS = 30.0


@dataclass(frozen=True)
class Frame:
    event: str | None
    id: int | None
    data: str | None
    comment: str | None


def _parse(block: str) -> Frame:
    fields: dict[str, str] = {}
    comment = None
    for line in block.splitlines():
        if line.startswith(":"):
            comment = line[1:].strip()
        elif ":" in line:
            name, value = line.split(":", 1)
            fields[name] = value.removeprefix(" ")
    event_id = fields.get("id")
    return Frame(
        fields.get("event"), int(event_id) if event_id else None, fields.get("data"), comment
    )


async def read_sse(
    app: ASGIApp,
    path: str,
    *,
    until: Callable[[list[Frame]], bool],
    headers: Mapping[str, str] | None = None,
) -> list[Frame]:
    """Collect frames until `until(frames)` is true or the server closes, then disconnect."""

    chunks: asyncio.Queue[bytes | None] = asyncio.Queue()
    disconnected = asyncio.Event()
    request_sent = False

    async def receive() -> Message:
        nonlocal request_sent
        if not request_sent:
            request_sent = True
            return {"type": "http.request", "body": b"", "more_body": False}
        await disconnected.wait()
        return {"type": "http.disconnect"}

    async def send(message: Message) -> None:
        if message["type"] == "http.response.start":
            assert message["status"] == 200, message
        elif message["type"] == "http.response.body":
            await chunks.put(message.get("body", b""))
            if not message.get("more_body", False):
                await chunks.put(None)

    scope = {
        "type": "http",
        "asgi": {"version": "3.0"},
        "http_version": "1.1",
        "method": "GET",
        "scheme": "http",
        "path": path,
        "raw_path": path.encode(),
        "query_string": b"",
        "root_path": "",
        "headers": [(k.lower().encode(), v.encode()) for k, v in (headers or {}).items()],
        "client": ("testclient", 50000),
        "server": ("testserver", 80),
    }

    async def serve() -> None:
        await app(scope, receive, send)

    task = asyncio.create_task(serve())
    frames: list[Frame] = []
    buffer = ""
    try:
        while not until(frames):
            chunk = await asyncio.wait_for(chunks.get(), READ_TIMEOUT_SECONDS)
            if chunk is None:
                break
            buffer += chunk.decode()
            *blocks, buffer = buffer.split("\n\n")
            frames.extend(_parse(block) for block in blocks if block.strip())
    finally:
        disconnected.set()
        await asyncio.wait_for(task, READ_TIMEOUT_SECONDS)
    return frames
