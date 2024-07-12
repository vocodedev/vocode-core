import asyncio
from typing import Dict

import pytest
from fastapi import WebSocket
from fastapi.websockets import WebSocketState
from pytest_mock import MockerFixture


@pytest.fixture
def incoming_websocket_messages():
    return asyncio.Queue()


@pytest.fixture
def outgoing_websocket_messages():
    return asyncio.Queue()


@pytest.fixture
def mock_ws(mocker: MockerFixture, incoming_websocket_messages, outgoing_websocket_messages):
    def create_receive(messages: asyncio.Queue[Dict]):
        async def receive():
            message = await messages.get()
            return message

        return receive

    def create_send(messages: asyncio.Queue[Dict]):
        async def send(message: Dict):
            messages.put_nowait(message)

        return send

    mock_ws = WebSocket(
        scope={"type": "websocket"}, receive=mocker.AsyncMock(), send=mocker.AsyncMock()
    )
    mock_ws.application_state = WebSocketState.CONNECTED
    mock_ws.receive = create_receive(incoming_websocket_messages)
    mock_ws.send = create_send(outgoing_websocket_messages)
    return mock_ws
