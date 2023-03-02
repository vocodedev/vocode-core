import websockets
import asyncio
from dotenv import load_dotenv
import os
import logging
import threading
import queue

load_dotenv()

from .input_device.base_input_device import BaseInputDevice
from .output_device.base_output_device import BaseOutputDevice
from .models.transcriber import TranscriberConfig
from .models.agent import AgentConfig
from .models.synthesizer import SynthesizerConfig
from .models.websocket import ReadyMessage, AudioMessage, StartMessage, StopMessage
from . import api_key

VOCODE_WEBSOCKET_URL = f'wss://api.vocode.dev/conversation'

class Conversation:

    def __init__(
        self,
        input_device: BaseInputDevice, 
        output_device: BaseOutputDevice, 
        transcriber_config: TranscriberConfig, 
        agent_config: AgentConfig,
        synthesizer_config: SynthesizerConfig
    ):
        self.input_device = input_device
        self.output_device = output_device
        self.transcriber_config = transcriber_config
        self.agent_config = agent_config
        self.synthesizer_config = synthesizer_config
        self.logger = logging.getLogger(__name__)
        self.receiver_ready = False
        self.active = True
        self.output_loop = asyncio.new_event_loop()
        self.output_audio_queue = queue.Queue()

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
                    await self.output_device.send_async(audio)
                except queue.Empty:
                    continue
        loop = asyncio.new_event_loop()
        loop.run_until_complete(run())
    
    async def start(self):
        async with websockets.connect(f"{VOCODE_WEBSOCKET_URL}?key={api_key}") as ws:
            async def sender(ws):
                start_message = StartMessage(
                    transcriber_config=self.transcriber_config, 
                    agent_config=self.agent_config, 
                    synthesizer_config=self.synthesizer_config
                )
                await ws.send(start_message.json())
                await self.wait_for_ready()
                self.logger.info("Listening...press Ctrl+C to stop")
                while self.active:
                    data = self.input_device.get_audio()
                    if data:
                        await ws.send(AudioMessage.from_bytes(data).json())
                        await asyncio.sleep(0)
                await ws.send(StopMessage().json())

            async def receiver(ws):
                ReadyMessage.parse_raw(await ws.recv())
                self.receiver_ready = True
                async for msg in ws:
                    audio_message = AudioMessage.parse_raw(msg)
                    self.output_audio_queue.put_nowait(audio_message.get_bytes())


            output_thread = threading.Thread(target=self.play_audio)
            output_thread.start()
            return await asyncio.gather(sender(ws), receiver(ws))

