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
from vocode.telephony.zoom_dial_in import ZoomDialIn

if __name__ == "__main__":
    call = ZoomDialIn(
        recipient=CallEntity(phone_number="<zoom_phone_number>"),
        caller=CallEntity(
            phone_number="<your_phone_number>",
        ),
        zoom_meeting_id="<zoom_meeting_id>",
        zoom_meeting_password="<zoom_meeting_password>",
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
    input("Press enter to end the call...")
    call.end()
