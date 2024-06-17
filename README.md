<div align="center">

![Hero](https://user-images.githubusercontent.com/6234599/228337850-e32bb01d-3701-47ef-a433-3221c9e0e56e.png)

[![Twitter](https://img.shields.io/twitter/url/https/twitter.com/vocodehq.svg?style=social&label=Follow%20%40vocodehq)](https://twitter.com/vocodehq) [![GitHub Repo stars](https://img.shields.io/github/stars/vocodedev/vocode-core?style=social)](https://github.com/vocodedev/vocode-core)
[![pypi](https://img.shields.io/pypi/v/vocode.svg)](https://pypi.python.org/pypi/vocode)
[![Downloads](https://static.pepy.tech/badge/vocode/month)](https://pepy.tech/project/vocode)

[Community](https://discord.gg/NaU4mMgcnC) | [Docs](https://docs.vocode.dev/open-source) | [Dashboard](https://app.vocode.dev)

</div>

# <span><img style='vertical-align:middle; display:inline;' src="https://user-images.githubusercontent.com/6234599/228339858-95a0873a-2d40-4542-963a-6358d19086f5.svg"  width="5%" height="5%">&nbsp; vocode</span>

### **Build voice-based LLM apps in minutes**

Vocode is an open source library that makes it easy to build voice-based LLM apps. Using Vocode, you can build real-time streaming conversations with LLMs and deploy them to phone calls, Zoom meetings, and more. You can also build personal assistants or apps like voice-based chess. Vocode provides easy abstractions and integrations so that everything you need is in a single library.

We're actively looking for community maintainers, so please reach out if interested!

# ⭐️ Features

- 🗣 [Spin up a conversation with your system audio](https://docs.vocode.dev/open-source/python-quickstart)
- ➡️ 📞 [Set up a phone number that responds with a LLM-based agent](https://docs.vocode.dev/open-source/telephony#inbound-calls)
- 📞 ➡️ [Send out phone calls from your phone number managed by an LLM-based agent](https://docs.vocode.dev/telephony/open-source/#outbound-calls)
- 🧑‍💻 [Dial into a Zoom call](https://github.com/vocodedev/vocode-core/blob/53b01dab0b59f71961ee83dbcaf3653a6935c2e3/vocode/streaming/telephony/conversation/zoom_dial_in.py)
- 🤖 [Use an outbound call to a real phone number in a Langchain agent](https://docs.vocode.dev/open-source/langchain-agent)
- Out of the box integrations with:
  - Transcription services, including:
    - [AssemblyAI](https://www.assemblyai.com/)
    - [Deepgram](https://deepgram.com/)
    - [Gladia](https://gladia.io)
    - [Google Cloud](https://cloud.google.com/speech-to-text)
    - [Microsoft Azure](https://azure.microsoft.com/en-us/products/cognitive-services/speech-to-text)
    - [RevAI](https://www.rev.ai/)
    - [Whisper](https://openai.com/blog/introducing-chatgpt-and-whisper-apis)
    - [Whisper.cpp](https://github.com/ggerganov/whisper.cpp)
  - LLMs, including:
    - [OpenAI](https://platform.openai.com/docs/models)
    - [Anthropic](https://www.anthropic.com/)
  - Synthesis services, including:
    - [Rime.ai](https://rime.ai)
    - [Microsoft Azure](https://azure.microsoft.com/en-us/products/cognitive-services/text-to-speech/)
    - [Google Cloud](https://cloud.google.com/text-to-speech)
    - [Play.ht](https://play.ht)
    - [Eleven Labs](https://elevenlabs.io/)
    - [Cartesia](https://cartesia.ai/)
    - [Coqui (OSS)](https://github.com/coqui-ai/TTS)
    - [gTTS](https://gtts.readthedocs.io/)
    - [StreamElements](https://streamelements.com/)
    - [Bark](https://github.com/suno-ai/bark)
    - [AWS Polly](https://aws.amazon.com/polly/)

Check out our React SDK [here](https://github.com/vocodedev/vocode-react-sdk)!

# 🫂 Contribution and Roadmap

We're an open source project and are extremely open to contributors adding new features, integrations, and documentation! Please don't hesitate to reach out and get started building with us.

For more information on contributing, see our [Contribution Guide](https://github.com/vocodedev/vocode-core/blob/main/contributing.md).

And check out our [Roadmap](https://github.com/vocodedev/vocode-core/blob/main/roadmap.md).

We'd love to talk to you on [Discord](https://discord.gg/NaU4mMgcnC) about new ideas and contributing!

# 🚀 Quickstart

```bash
pip install vocode
```

```python
import asyncio
import signal

from pydantic_settings import BaseSettings, SettingsConfigDict

from vocode.helpers import create_streaming_microphone_input_and_speaker_output
from vocode.logging import configure_pretty_logging
from vocode.streaming.agent.chat_gpt_agent import ChatGPTAgent
from vocode.streaming.models.agent import ChatGPTAgentConfig
from vocode.streaming.models.message import BaseMessage
from vocode.streaming.models.synthesizer import AzureSynthesizerConfig
from vocode.streaming.models.transcriber import (
    DeepgramTranscriberConfig,
    PunctuationEndpointingConfig,
)
from vocode.streaming.streaming_conversation import StreamingConversation
from vocode.streaming.synthesizer.azure_synthesizer import AzureSynthesizer
from vocode.streaming.transcriber.deepgram_transcriber import DeepgramTranscriber

configure_pretty_logging()


class Settings(BaseSettings):
    """
    Settings for the streaming conversation quickstart.
    These parameters can be configured with environment variables.
    """

    openai_api_key: str = "ENTER_YOUR_OPENAI_API_KEY_HERE"
    azure_speech_key: str = "ENTER_YOUR_AZURE_KEY_HERE"
    deepgram_api_key: str = "ENTER_YOUR_DEEPGRAM_API_KEY_HERE"

    azure_speech_region: str = "eastus"

    # This means a .env file can be used to overload these settings
    # ex: "OPENAI_API_KEY=my_key" will set openai_api_key over the default above
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )


settings = Settings()


async def main():
    (
        microphone_input,
        speaker_output,
    ) = create_streaming_microphone_input_and_speaker_output(
        use_default_devices=False,
    )

    conversation = StreamingConversation(
        output_device=speaker_output,
        transcriber=DeepgramTranscriber(
            DeepgramTranscriberConfig.from_input_device(
                microphone_input,
                endpointing_config=PunctuationEndpointingConfig(),
                api_key=settings.deepgram_api_key,
            ),
        ),
        agent=ChatGPTAgent(
            ChatGPTAgentConfig(
                openai_api_key=settings.openai_api_key,
                initial_message=BaseMessage(text="What up"),
                prompt_preamble="""The AI is having a pleasant conversation about life""",
            )
        ),
        synthesizer=AzureSynthesizer(
            AzureSynthesizerConfig.from_output_device(speaker_output),
            azure_speech_key=settings.azure_speech_key,
            azure_speech_region=settings.azure_speech_region,
        ),
    )
    await conversation.start()
    print("Conversation started, press Ctrl+C to end")
    signal.signal(signal.SIGINT, lambda _0, _1: asyncio.create_task(conversation.terminate()))
    while conversation.is_active():
        chunk = await microphone_input.get_audio()
        conversation.receive_audio(chunk)


if __name__ == "__main__":
    asyncio.run(main())
```

# 📞 Phone call quickstarts

- [Telephony Server - Self-hosted](https://docs.vocode.dev/open-source/telephony)

# 🌱 Documentation

[docs.vocode.dev](https://docs.vocode.dev/open-source)
