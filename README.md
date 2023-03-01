# vocode Python SDK

```
pip install vocode
```

```python
import asyncio
import signal

from vocode.conversation import Conversation
from vocode.helpers import create_microphone_input_and_speaker_output
from vocode.models.transcriber import DeepgramTranscriberConfig
from vocode.models.agent import LLMAgentConfig
from vocode.models.synthesizer import AzureSynthesizerConfig

if __name__ == "__main__":
    microphone_input, speaker_output = create_microphone_input_and_speaker_output(use_first_available_device=True)

    conversation = Conversation(
        input_device=microphone_input,
        output_device=speaker_output,
        transcriber_config=DeepgramTranscriberConfig.from_input_device(microphone_input),
        agent_config=LLMAgentConfig(prompt_preamble="The AI is having a pleasant conversation about life."),
        synthesizer_config=AzureSynthesizerConfig.from_output_device(speaker_output)
    )
    signal.signal(signal.SIGINT, lambda _0, _1: conversation.deactivate())
    asyncio.run(conversation.start())
```
