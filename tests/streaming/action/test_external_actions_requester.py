import base64
import hashlib
import hmac
import json
import os
from typing import Any, Callable, Dict

import httpx
import pytest
from httpx import Request, Response
from pytest_httpx import HTTPXMock

from vocode.streaming.action.external_actions_requester import ExternalActionsRequester

JSON_SCHEMA = {
    "type": "object",
    "properties": {
        "length": {
            "type": "string",
            "enum": ["30m", "1hr"],
        },
        "time": {
            "type": "string",
            "pattern": r"^\d{2}:\d0[ap]m$",
        },
    },
}


@pytest.fixture
def mock_async_client_post(status_code: int, json_response: Dict[str, Any]) -> Callable:
    async def mock_post(self, url: str, content: str, headers: Dict[str, str] = None) -> Response:
        request = Request(method="POST", url=url, headers=headers, content=content)
        return Response(status_code, json=json_response, request=request)

    return mock_post


@pytest.fixture
def requester() -> ExternalActionsRequester:
    return ExternalActionsRequester("http://test.com")


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "status_code,json_response,expected_success",
    [
        (200, {"result": {"key": "value"}, "agent_message": "Success", "success": True}, True),
        (400, {"detail": "Bad Request"}, False),
        (401, {"detail": "Unauthorized"}, False),
        (403, {"detail": "Forbidden"}, False),
        (500, {"detail": "Server Error"}, False),
    ],
)
async def test_send_request_responses(
    httpx_mock: HTTPXMock,
    status_code: int,
    json_response: Dict[str, Any],
    expected_success: bool,
) -> None:
    url = "http://test.com"
    httpx_mock.add_response(status_code=status_code, json=json_response, method="POST", url=url)

    requester = ExternalActionsRequester(url)
    response = await requester.send_request(
        JSON_SCHEMA,
        base64.b64encode(os.urandom(32)).decode(),
        additional_payload_values={"call_id": "call_id"},
        additional_headers={"x-vocode-test": "test"},
        transport=httpx.AsyncHTTPTransport(retries=3, verify=True),
    )

    assert httpx_mock.get_request().headers["x-vocode-test"] == "test"
    assert "x-vocode-signature" in httpx_mock.get_request().headers

    assert response.success is expected_success


@pytest.mark.asyncio
async def test_requester_encodes_signature_correctly(requester: ExternalActionsRequester):
    payload = json.dumps({"test": "test"}).encode("utf-8")
    signature_as_bytes = os.urandom(32)
    signature = base64.b64encode(signature_as_bytes).decode()

    encoded_payload = requester._encode_payload(payload, signature)
    decoded_digest = base64.b64decode(encoded_payload)
    calculated_digest = hmac.new(signature_as_bytes, payload, hashlib.sha256).digest()
    assert hmac.compare_digest(decoded_digest, calculated_digest)
