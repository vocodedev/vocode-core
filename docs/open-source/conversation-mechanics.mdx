---
title: "Conversation Mechanics"
description: "How to tune the responsiveness in Vocode conversations"
---

Building two-way conversations with an AI is a highly use-case specific task - how realistic the conversation is depends greatly on the nature of the conversation itself. In this guide, we'll cover some of the dials you can turn to configure the mechanics of a conversation in Vocode.

# Endpointing

Endpointing is the process of understanding when someone has finished speaking. The `EndpointingConfig` controls how this is done. There are a couple of different ways to configure endpointing:

We provide `DeepgramEndpointingConfig()` which has some reasonable defaults and knobs to suit most use-cases (but only works with the Deepgram transcriber).

```
class DeepgramEndpointingConfig(EndpointingConfig, type="deepgram"):  # type: ignore
    vad_threshold_ms: int = 500
    utterance_cutoff_ms: int = 1000
    time_silent_config: Optional[TimeSilentConfig] = Field(default_factory=TimeSilentConfig)
    use_single_utterance_endpointing_for_first_utterance: bool = False
```

- `vad_threshold_ms`: translates to [Deepgram's `endpointing` feature](https://developers.deepgram.com/docs/endpointing#enable-feature)
- `utterance_cutoff_ms`: uses [Deepgram's Utterance End features](https://developers.deepgram.com/docs/utterance-end)
- `time_silent_config`: is a Vocode specific parameter that marks an utterance final if we haven't seen any new words in X seconds
- `use_single_utterance_endpointing_for_first_utterance`: Uses `is_final` instead of `speech_final` for endpointing for the first utterance (works really well for outbound conversations, where the user's first utterance is something like "Hello?") - see [this doc on Deepgram](https://developers.deepgram.com/docs/understand-endpointing-interim-results) for more info.

Endpointing is highly use-case specific - building a realistic experience for this greatly depends on the person speaking to the AI. Here are few paradigms that we've used to help you along the way:

- Time-based endpointing: This method considers the speaker to be finished when there is a certain duration of silence.
- Punctuation-based endpointing: This method considers the speaker to be finished when there is a certain duration of silence after a punctuation mark.

# Interruptions

When the AI speaks in a `StreamingConversation`, it can be interrupted by the user. `AgentConfig` itself provides a parameter called `interrupt_sensitivity` that can be used to control how sensitive the AI is to interruptions. Interrupt sensitivity has two options: low (default) and high. Low sensitivity makes the bot ignore backchannels (e.g. “sure”, “uh-huh”) while the bot is speaking. High sensitivity makes the agent treat any word from the human as an interruption.

The implementation of this configuration is in `StreamingConversation.TranscriptionsWorker` - in order to make this work well, you may need to fork Vocode and override this behavior, but it provides a good starting place for most use-cases.

Stay tuned, more dials to come here soon!

# Conversation Speed

`StreamingConversation` also exposes a parameter called `conversation_speed`, which controls the length of endpointing pauses, i.e. how long the bot will wait before responding to the human. This includes normal utterances from the human as well as interruptions.

The amount of time the bot waits inversely scales with the `conversation_speed` value. So a bot with `conversation_speed` of 2 responds in half the time compared to a `conversation_speed` of 1. Likewise a `conversation_speed` of 0.5 means the bot takes twice as long to respond.

```python
conversation = StreamingConversation(
    speed_coefficient=2
    ...
)
```

Based on the speed of the user's speech (we calculate the WPM from each final utterance that goes through the pipeline), the `speed_coefficient` updates throughout the course of the conversation - see `vocode.streaming.utils.speed_manager` to see this implementation!
