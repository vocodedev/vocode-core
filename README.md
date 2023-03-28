<div align="center">

![Hero](https://user-images.githubusercontent.com/6234599/228337850-e32bb01d-3701-47ef-a433-3221c9e0e56e.png)

    
[![Twitter](https://img.shields.io/twitter/url/https/twitter.com/vocodehq.svg?style=social&label=Follow%20%40vocodehq)](https://twitter.com/vocodehq) [![GitHub Repo stars](https://img.shields.io/github/stars/vocodedev/vocode-python?style=social)](https://github.com/vocodedev/vocode-python)

[Community](https://discord.gg/NaU4mMgcnC) | [Docs](https://docs.vocode.dev) | [Dashboard](https://app.vocode.dev)
</div>

```
pip install vocode
```

```python
import asyncio
import signal
import vocode

vocode.api_key = "YOUR_API_KEY"

from vocode.conversation import Conversation
from vocode.helpers import create_microphone_input_and_speaker_output
from vocode.models.transcriber import DeepgramTranscriberConfig
from vocode.models.agent import ChatGPTAgentConfig
from vocode.models.synthesizer import AzureSynthesizerConfig

if __name__ == "__main__":
    microphone_input, speaker_output = create_microphone_input_and_speaker_output(
        use_default_devices=True
    )

    conversation = Conversation(
        input_device=microphone_input,
        output_device=speaker_output,
        transcriber_config=DeepgramTranscriberConfig.from_input_device(microphone_input),
        agent_config=ChatGPTAgentConfig(
          initial_message=BaseMessage(text="Hello!"),
          prompt_preamble="The AI is having a pleasant conversation about life."
        ),
        synthesizer_config=AzureSynthesizerConfig.from_output_device(speaker_output)
    )
    # This allows you to stop the conversation with a KeyboardInterrupt
    signal.signal(signal.SIGINT, lambda _0, _1: conversation.deactivate())
    asyncio.run(conversation.start())
```
