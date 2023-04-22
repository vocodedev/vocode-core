import logging
import os
from langchain.agents import tool
from dotenv import load_dotenv

load_dotenv()

from vocode.streaming.telephony.conversation.outbound_call import OutboundCall
from vocode.streaming.telephony.config_manager.redis_config_manager import (
    RedisConfigManager,
)
from vocode.streaming.models.agent import ChatGPTAgentConfig
import time


@tool("call phone number")
def call_phone_number(input: str) -> str:
    """calls a phone number as a bot and returns a transcript of the conversation. 
    the input to this tool is a comma separated list of a phone number and a prompt. 
    The prompt should instruct the bot with what to do on the call and be in the 3rd person, 
    like 'the AI is performing this task' instead of 'perform this task'.

    for example, `+15555555555,the AI is explaining the meaning of life` will call +15555555555 with and instruct the AI to tell the human what the meaning of life is.
    """
    phone_number, prompt = input.split(",", 1)
    call = OutboundCall(
        base_url=os.getenv("TELEPHONY_SERVER_BASE_URL"),
        to_phone=phone_number,
        from_phone=os.getenv("OUTBOUND_CALLER_NUMBER"),
        config_manager=RedisConfigManager(),
        agent_config=ChatGPTAgentConfig(prompt_preamble=prompt, end_conversation_on_goodbye=True, model_name="gpt-4"),
        logger=logging.Logger("call_phone_number"),
    )
    call.start()
    while True:
        transcript_filename = "examples/agent_demo/call_transcripts/{}.txt".format(call.conversation_id)
        if os.path.exists(transcript_filename):
            with open(transcript_filename) as f:
                return f.read()
        else:
            time.sleep(1)
    
