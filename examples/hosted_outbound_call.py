from vocode.streaming.models.synthesizer import AzureSynthesizerConfig
from vocode.streaming.output_device.telephone_output import TelephoneOutput
from vocode.streaming.telephony.hosted.outbound_call import OutboundCall
from vocode.streaming.models.telephony import CallEntity
from vocode.streaming.models.agent import (
    EchoAgentConfig,
    ChatGPTAgentConfig,
    WebSocketUserImplementedAgentConfig,
)
from vocode.streaming.models.message import BaseMessage
from vocode.streaming.telephony.hosted.zoom_dial_in import ZoomDialIn

if __name__ == "__main__":
    call = ZoomDialIn(
        recipient=CallEntity(phone_number="<your zoom phone number>"),
        caller=CallEntity(
            phone_number="<your phone number>",
        ),
        zoom_meeting_id="<your zoom meeting id>",
        zoom_meeting_password="<your zoom meeting password>",
        agent_config=ChatGPTAgentConfig(
            initial_message=BaseMessage(text="the quick fox jumped over the lazy dog "),
            prompt_preamble="respond two sentences at a time",
            generate_responses=True,
            end_conversation_on_goodbye=True,
            send_filler_audio=True,
            allowed_idle_time_seconds=30,
        ),
        synthesizer_config=AzureSynthesizerConfig.from_output_device(
            output_device=TelephoneOutput(), voice_name="en-US-JennyNeural"
        ),
    )
    call.start()
    input("Press enter to end the call...")
    call.end()
