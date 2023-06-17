from typing import TYPE_CHECKING, Optional
from vocode.streaming.models.transcriber import EndpointingConfig

if TYPE_CHECKING:
    from vocode.streaming.streaming_conversation import StreamingConversation


class ConversationStateManager:
    def __init__(self, conversation: "StreamingConversation"):
        self._conversation = conversation

    def get_transcriber_endpointing_config(self) -> Optional[EndpointingConfig]:
        return (
            self._conversation.transcriber.get_transcriber_config().endpointing_config
        )

    def set_transcriber_endpointing_config(self, endpointing_config: EndpointingConfig):
        assert self.get_transcriber_endpointing_config() is not None
        self._conversation.transcriber.get_transcriber_config().endpointing_config = (
            endpointing_config
        )
