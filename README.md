<div align="center">

![Hero](https://user-images.githubusercontent.com/6234599/228337850-e32bb01d-3701-47ef-a433-3221c9e0e56e.png)

[![Twitter](https://img.shields.io/twitter/url/https/twitter.com/vocodehq.svg?style=social&label=Follow%20%40vocodehq)](https://twitter.com/vocodehq) [![GitHub Repo stars](https://img.shields.io/github/stars/vocodedev/vocode-python?style=social)](https://github.com/vocodedev/vocode-python)

[Community](https://discord.gg/NaU4mMgcnC) | [Docs](https://docs.vocode.dev) | [Dashboard](https://app.vocode.dev)

</div>

# <span><img style='vertical-align:middle; display:inline;' src="https://user-images.githubusercontent.com/6234599/228339858-95a0873a-2d40-4542-963a-6358d19086f5.svg"  width="5%" height="5%">&nbsp; vocode</span>

### **Build voice-based LLM apps in minutes**

Vocode is an open source library that makes it easy to build voice-based LLM apps. Using Vocode, you can build real-time streaming conversations with LLMs and deploy them to phone calls, Zoom meetings, and more. You can also build personal assistants or apps like voice-based chess. Vocode provides easy abstractions and integrations so that everything you need is in a single library.

# ⭐️ Features

- 🗣 [Spin up a conversation with your system audio](https://docs.vocode.dev/python-quickstart)
- ➡️ 📞 [Set up a phone number that responds with a LLM-based agent](https://docs.vocode.dev/telephony#inbound-calls)
- 📞 ➡️ [Send out phone calls from your phone number managed by an LLM-based agent](https://docs.vocode.dev/telephony#outbound-calls)
- 🧑‍💻 [Dial into a Zoom call](https://github.com/vocodedev/vocode-python/blob/main/vocode/streaming/telephony/hosted/zoom_dial_in.py)
- Out of the box integrations with:
  - Transcription services, including:
    - [Deepgram](https://deepgram.com/)
    - [AssemblyAI](https://www.assemblyai.com/)
    - [Google Cloud](https://cloud.google.com/speech-to-text)
    - [Whisper](https://openai.com/blog/introducing-chatgpt-and-whisper-apis)
    - [RevAI](https://www.rev.ai/)
  - LLMs, including:
    - [ChatGPT](https://openai.com/blog/chatgpt)
    - [GPT-4](https://platform.openai.com/docs/models/gpt-4)
    - [Anthropic](https://www.anthropic.com/) - coming soon!
  - Synthesis services, including:
    - [Rime.ai](https://rime.ai)
    - [Microsoft Azure](https://azure.microsoft.com/en-us/products/cognitive-services/text-to-speech/)
    - [Google Cloud](https://cloud.google.com/text-to-speech)
    - [Play.ht](https://play.ht)
    - [Eleven Labs](https://elevenlabs.io/)

Check out our React SDK [here](https://github.com/vocodedev/vocode-react-sdk)!

# 🫂 Contribution

We'd love for you all to build on top of our abstractions to enable new and better LLM voice applications!

You can extend our [`BaseAgent`](https://github.com/vocodedev/vocode-python/blob/main/vocode/streaming/agent/base_agent.py), [`BaseTranscriber`](https://github.com/vocodedev/vocode-python/blob/main/vocode/streaming/transcriber/base_transcriber.py), and [`BaseSynthesizer`](https://github.com/vocodedev/vocode-python/blob/main/vocode/streaming/synthesizer/base_synthesizer.py) abstractions to integrate with new LLM APIs, speech recognition and speech synthesis providers. More detail [here](https://docs.vocode.dev/create-your-own-agent#self-hosted).

You can also work with our [`BaseInputDevice`](https://github.com/vocodedev/vocode-python/blob/main/vocode/streaming/input_device/base_input_device.py) and [`BaseOutputDevice`](https://github.com/vocodedev/vocode-python/blob/main/vocode/streaming/output_device/base_output_device.py) abstractions to set up voice applications on new surfaces/platforms. More guides for this coming soon!

Because our [`StreamingConversation`](https://github.com/vocodedev/vocode-python/blob/main/vocode/streaming/streaming_conversation.py) runs locally, it's relatively quick to develop on! Feel free to fork and create a PR and we will get it merged as soon as possible. And we'd love to talk to you on [Discord](https://discord.gg/NaU4mMgcnC)!

# 🚀 Quickstart (Self-hosted)

```bash
pip install 'vocode[io]'
```

```python
import asyncio
import signal

import vocode
from vocode.streaming.streaming_conversation import StreamingConversation
from vocode.helpers import create_microphone_input_and_speaker_output
from vocode.streaming.models.transcriber import (
    DeepgramTranscriberConfig,
    PunctuationEndpointingConfig,
)
from vocode.streaming.agent.chat_gpt_agent import ChatGPTAgent
from vocode.streaming.models.agent import ChatGPTAgentConfig
from vocode.streaming.models.message import BaseMessage
from vocode.streaming.models.synthesizer import AzureSynthesizerConfig
from vocode.streaming.synthesizer.azure_synthesizer import AzureSynthesizer
from vocode.streaming.transcriber.deepgram_transcriber import DeepgramTranscriber

# these can also be set as environment variables
vocode.setenv(
    OPENAI_API_KEY="<your OpenAI key>",
    DEEPGRAM_API_KEY="<your Deepgram key>",
    AZURE_SPEECH_KEY="<your Azure key>",
    AZURE_SPEECH_REGION="<your Azure region>",
)


async def main():
    microphone_input, speaker_output = create_microphone_input_and_speaker_output(
        streaming=True, use_default_devices=False
    )

    conversation = StreamingConversation(
        output_device=speaker_output,
        transcriber=DeepgramTranscriber(
            DeepgramTranscriberConfig.from_input_device(
                microphone_input, endpointing_config=PunctuationEndpointingConfig()
            )
        ),
        agent=ChatGPTAgent(
            ChatGPTAgentConfig(
                initial_message=BaseMessage(text="Hello!"),
                prompt_preamble="Have a pleasant conversation about life",
            ),
        ),
        synthesizer=AzureSynthesizer(
            AzureSynthesizerConfig.from_output_device(speaker_output)
        ),
    )
    await conversation.start()
    print("Conversation started, press Ctrl+C to end")
    signal.signal(signal.SIGINT, lambda _0, _1: conversation.terminate())
    while conversation.is_active():
        chunk = microphone_input.get_audio()
        if chunk:
            conversation.receive_audio(chunk)
        await asyncio.sleep(0)


if __name__ == "__main__":
    asyncio.run(main())
```

# ☁️ Quickstart (Hosted)

First, get a _free_ API key from our [dashboard](https://app.vocode.dev).

```bash
pip install 'vocode[io]'
```

```python
import asyncio
import signal

import vocode
from vocode.streaming.hosted_streaming_conversation import HostedStreamingConversation
from vocode.streaming.streaming_conversation import StreamingConversation
from vocode.helpers import create_microphone_input_and_speaker_output
from vocode.streaming.models.transcriber import (
    DeepgramTranscriberConfig,
    PunctuationEndpointingConfig,
)
from vocode.streaming.models.agent import ChatGPTAgentConfig
from vocode.streaming.models.message import BaseMessage
from vocode.streaming.models.synthesizer import AzureSynthesizerConfig

vocode.api_key = "<your API key>"


if __name__ == "__main__":
    microphone_input, speaker_output = create_microphone_input_and_speaker_output(
        streaming=True, use_default_devices=False
    )

    conversation = HostedStreamingConversation(
        input_device=microphone_input,
        output_device=speaker_output,
        transcriber_config=DeepgramTranscriberConfig.from_input_device(
            microphone_input,
            endpointing_config=PunctuationEndpointingConfig(),
        ),
        agent_config=ChatGPTAgentConfig(
            initial_message=BaseMessage(text="Hello!"),
            prompt_preamble="Have a pleasant conversation about life",
        ),
        synthesizer_config=AzureSynthesizerConfig.from_output_device(speaker_output),
    )
    signal.signal(signal.SIGINT, lambda _0, _1: conversation.deactivate())
    asyncio.run(conversation.start())
```

# 📞 Phone call quickstarts

- [Inbound calls - Hosted](https://docs.vocode.dev/telephony#inbound-calls)
- [Outbound calls - Hosted](https://docs.vocode.dev/telephony#outbound-calls)
- [Telephony Server - Self-hosted](https://github.com/vocodedev/vocode-python/blob/main/examples/telephony_app.py)

# 🌱 Documentation

[docs.vocode.dev](https://docs.vocode.dev/)
