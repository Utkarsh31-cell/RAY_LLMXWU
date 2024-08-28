import json
from collections import namedtuple
from typing import AsyncIterator, Dict, Union

import aiohttp

from rayllm.common.constants import TIMEOUT
from rayllm.common.utils import (
    ResponseError,
    _is_aviary_model,
)
from rayllm.frontend.endpoints_sdk import get_endpoints_backend

from ..sdk import get_aviary_backend

__all__ = ["stream"]

response = namedtuple("Response", ["text", "status_code"])


# We are reimplementing the sdk here in async as openai package is not async
# Without async, the tokens would be printed very slowly making for bad UX in
# the frontend
async def stream(
    model: str, prompt: str, backend: str = "aviary"
) -> AsyncIterator[Dict[str, Union[str, float, int]]]:
    """Query Aviary and stream response"""
    r = None
    if _is_aviary_model(model):
        if backend == "aviary":
            backend = get_aviary_backend()
        elif backend == "endpoints":
            backend = get_endpoints_backend()
        else:
            raise ValueError(f"Expected one of 'aviary' or 'endpoints. Got: {backend}")
        url = backend.backend_url + "/chat/completions"
        headers = {"Authorization": f"{backend.bearer}"}

        chunk = b""
        try:
            async with aiohttp.ClientSession(
                raise_for_status=True, headers=headers
            ) as session:
                async with session.post(
                    url,
                    json={
                        "model": model,
                        "messages": [{"role": "user", "content": prompt}],
                        "stream": True,
                    },
                    timeout=TIMEOUT[-1],
                ) as r:
                    async for chunk in r.content:
                        chunk = chunk.replace(b"data: ", b"").strip()
                        if not chunk or chunk == b"[DONE]":
                            continue
                        data = json.loads(chunk)
                        if data.get("error"):
                            raise ResponseError(
                                data["error"],
                                response=response(data["error"], r.status),
                            )
                        yield data
        except Exception as e:
            if isinstance(e, ResponseError):
                raise e
            else:
                status = r.status if r else 500
                raise ResponseError(
                    str(e), response=response(chunk.decode("utf-8"), status)
                ) from e
    else:
        raise RuntimeError("Streaming is currently only supported for aviary models")
