import base64
import hashlib
import hmac
import json
from typing import Any, Dict, Optional

import httpx
from loguru import logger
from pydantic.v1 import BaseModel


class ExternalActionValueError(ValueError):
    pass


class ExternalActionsErrorResponses:
    client_error = (
        "There was an error with the information provided. "
        "Please ask for clarification and try again."
    )
    server_error = (
        "There was a server error with status "
        "{status}: {text}. Please politely tell the user to try again later."
    )
    input_error = (
        "There was an error with the information received from the service. "
        "Please politely tell the user to try again later."
        "\nThe error was {error}"
    )
    unauthorized = (
        "There was an error with the authentication for the service. "
        "Please politely tell the user to try again later."
    )
    forbidden = (
        "There was an error with the authentication for the service. "
        "Please politely tell the user to try again later."
    )


class ExternalActionResponse(BaseModel):
    result: dict
    success: bool
    agent_message: Optional[str] = None


class ExternalActionsRequester:
    def __init__(self, url: str) -> None:
        self.url = url

    async def send_request(
        self,
        payload: Dict[str, Any],
        signature_secret: str,
        additional_payload_values: Dict[str, Any] = {},
    ) -> ExternalActionResponse:
        encoded_payload = json.dumps({"payload": payload} | additional_payload_values).encode(
            "utf-8"
        )

        headers = {
            "Accept": "application/json",
            "Content-Type": "application/json",
            "x-vocode-signature": self._encode_payload(encoded_payload, signature_secret),
        }

        transport = httpx.AsyncHTTPTransport(retries=2)
        async with httpx.AsyncClient(
            headers=headers,
            transport=transport,
            timeout=10,
        ) as client:
            try:
                response = await client.post(
                    self.url,
                    content=encoded_payload,
                )
                response.raise_for_status()
                data = response.json()
                return self._validate_response(data)
            except httpx.HTTPStatusError as e:
                logger.error(f"[External Actions] Request failed: {e}")
                if e.response.status_code == 401:
                    return ExternalActionResponse(
                        result={"info": ExternalActionsErrorResponses.unauthorized},
                        success=False,
                    )
                elif e.response.status_code == 403:
                    return ExternalActionResponse(
                        result={"info": ExternalActionsErrorResponses.forbidden},
                        success=False,
                    )
                if 400 <= e.response.status_code < 500:
                    return ExternalActionResponse(
                        result={"info": ExternalActionsErrorResponses.client_error},
                        success=False,
                    )
                elif e.response.status_code >= 500:
                    return ExternalActionResponse(
                        result={
                            "info": ExternalActionsErrorResponses.server_error.format(
                                status=e.response.status_code, text=e.response.text
                            )
                        },
                        success=False,
                    )
                else:
                    raise e
            except ExternalActionValueError as e:
                return ExternalActionResponse(
                    result={"info": ExternalActionsErrorResponses.input_error.format(error=str(e))},
                    success=False,
                )

    def _encode_payload(self, payload: bytes, signature_secret: str) -> str:
        signature_as_bytes = base64.b64decode(signature_secret)
        digest = hmac.new(signature_as_bytes, payload, hashlib.sha256).digest()
        return base64.b64encode(digest).decode()

    def _validate_response(self, response: Dict[str, Any]) -> ExternalActionResponse:
        if "result" not in response:
            raise ExternalActionValueError("Invalid response format: missing 'result'")
        if not isinstance(response["result"], dict):
            raise ExternalActionValueError(
                "Invalid response format: 'agent_message' must be a key value map"
            )
        if "agent_message" in response and not isinstance(response["agent_message"], str):
            raise ExternalActionValueError(
                "Invalid response format: 'agent_message' must be a string"
            )
        return ExternalActionResponse(
            result=response["result"],
            agent_message=response.get("agent_message"),
            success=True,
        )
