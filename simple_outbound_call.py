from vocode.models.synthesizer import AzureSynthesizerConfig
from vocode.output_device.telephone_output import TelephoneOutput
from vocode.telephony.outbound_call import OutboundCall
from vocode.models.telephony import CallEntity
from vocode.models.agent import (
    EchoAgentConfig,
    ChatGPTAgentConfig,
    WebSocketUserImplementedAgentConfig,
)
from vocode.models.message import BaseMessage

if __name__ == "__main__":
    call = OutboundCall(
        recipient=CallEntity(
            phone_number="+11234567890",
        ),
        caller=CallEntity(
            phone_number="+11234567890",
        ),
        agent_config=ChatGPTAgentConfig(
            initial_message=BaseMessage(text="the quick fox jumped over the lazy dog "),
            prompt_preamble="respond two sentences at a time",
            generate_responses=True,
            end_conversation_on_goodbye=True,
            send_filler_audio=True,
        ),
        synthesizer_config=AzureSynthesizerConfig.from_output_device(
            output_device=TelephoneOutput(), voice_name="en-US-JennyNeural"
        ),
    )
    call.start()
