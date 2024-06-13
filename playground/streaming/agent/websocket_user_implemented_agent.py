import asyncio

from websockets.server import serve

from vocode.streaming.models.websocket_agent import (
    WebSocketAgentMessage,
    WebSocketAgentStopMessage,
    WebSocketAgentTextMessage,
)


async def echo(websocket):
    async for message in websocket:
        message = WebSocketAgentMessage.parse_raw(message)
        if isinstance(message, WebSocketAgentTextMessage):
            text = message.data.text
            print("Conversation ID", message.conversation_id)
            if "bye" in text:
                response = WebSocketAgentStopMessage()
            else:
                response = WebSocketAgentTextMessage.from_text(message.data.text)
        await websocket.send(response.json())


async def main():
    async with serve(echo, "localhost", 3001):
        await asyncio.Future()  # run forever


asyncio.run(main())
