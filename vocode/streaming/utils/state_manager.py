from typing import TYPE_CHECKING, Optional
from vocode.streaming.models.transcriber import EndpointingConfig

if TYPE_CHECKING:
    from vocode.streaming.streaming_conversation import StreamingConversation
    from vocode.streaming.telephony.conversation.vonage_call import VonageCall
    from vocode.streaming.telephony.conversation.twilio_call import TwilioCall


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
    
    def disable_synthesis(self):
        self._conversation.synthesis_enabled = False
    
    def enable_synthesis(self):
        self._conversation.synthesis_enabled = True


class VonageCallStateManager(ConversationStateManager):
    def __init__(self, call: "VonageCall"):
        super().__init__(call)
        self._call = call


class TwilioCallStateManager(ConversationStateManager):
    def __init__(self, call: "TwilioCall"):
        super().__init__(call)
        self._call = call
