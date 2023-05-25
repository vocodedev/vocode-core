from __future__ import annotations

from typing import Optional
import websockets
from websockets.exceptions import ConnectionClosedOK
from websockets.client import WebSocketClientProtocol
import asyncio
import logging
import threading
import queue
import vocode
from vocode.streaming.input_device.base_input_device import (
    BaseInputDevice,
)
from vocode.streaming.output_device.base_output_device import BaseOutputDevice
from vocode.streaming.models.transcriber import TranscriberConfig
from vocode.streaming.models.agent import AgentConfig
from vocode.streaming.models.synthesizer import SynthesizerConfig
from vocode.streaming.models.websocket import (
    ReadyMessage,
    AudioMessage,
    StartMessage,
    StopMessage,
)


class HostedStreamingConversation:
    def __init__(
        self,
        input_device: BaseInputDevice,
        output_device: BaseOutputDevice,
        transcriber_config: TranscriberConfig,
        agent_config: AgentConfig,
        synthesizer_config: SynthesizerConfig,
        id: Optional[str] = None,
    ):
        self.id = id
        self.input_device = input_device
        self.output_device = output_device
        self.transcriber_config = transcriber_config
        self.agent_config = agent_config
        self.synthesizer_config = synthesizer_config
        self.logger = logging.getLogger(__name__)
        self.receiver_ready = False
        self.active = True
        self.output_loop = asyncio.new_event_loop()
        self.output_audio_queue: queue.Queue[bytes] = queue.Queue()
        self.vocode_websocket_url = f"wss://{vocode.base_url}/conversation"

    async def wait_for_ready(self):
        while not self.receiver_ready:
            await asyncio.sleep(0.1)
        return True

    def deactivate(self):
        self.active = False

    def play_audio(self):
        async def run():
            while self.active:
                try:
                    audio = self.output_audio_queue.get(timeout=5)
                    self.output_device.consume_nonblocking(audio)
                except queue.Empty:
                    continue

        loop = asyncio.new_event_loop()
        loop.run_until_complete(run())

    async def start(self):
        async with websockets.connect(
            f"{self.vocode_websocket_url}?key={vocode.api_key}"
        ) as ws:

            async def sender(ws: WebSocketClientProtocol):
                start_message = StartMessage(
                    transcriber_config=self.transcriber_config,
                    agent_config=self.agent_config,
                    synthesizer_config=self.synthesizer_config,
                    conversation_id=self.id,
                )
                await ws.send(start_message.json())
                await self.wait_for_ready()
                self.logger.info("Listening...press Ctrl+C to stop")
                while self.active:
                    data = await self.input_device.get_audio()
                    if data:
                        try:
                            await ws.send(AudioMessage.from_bytes(data).json())
                        except ConnectionClosedOK:
                            self.deactivate()
                            return
                        await asyncio.sleep(0)
                await ws.send(StopMessage().json())

            async def receiver(ws: WebSocketClientProtocol):
                ReadyMessage.parse_raw(await ws.recv())
                self.receiver_ready = True
                async for msg in ws:
                    audio_message = AudioMessage.parse_raw(msg)
                    self.output_audio_queue.put_nowait(audio_message.get_bytes())

            output_thread = threading.Thread(target=self.play_audio)
            output_thread.start()
            return await asyncio.gather(sender(ws), receiver(ws))
