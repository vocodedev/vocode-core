import logging
import sys
import os
from fastapi import FastAPI

# sys.path.insert(0, "/vocode")

from vocode.streaming.models.agent import ChatGPTAgentConfig
from vocode.streaming.models.synthesizer import ElevenLabsSynthesizerConfig
from vocode.streaming.synthesizer.eleven_labs_synthesizer import ElevenLabsSynthesizer

from vocode.streaming.agent.chat_gpt_agent import ChatGPTAgent
from vocode.streaming.client_backend.conversation import ConversationRouter
from vocode.streaming.models.message import BaseMessage

from dotenv import load_dotenv

load_dotenv()

app = FastAPI(docs_url=None)

logging.basicConfig()
logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)

conversation_router = ConversationRouter(
    agent=ChatGPTAgent(
        ChatGPTAgentConfig(
            initial_message=BaseMessage(text="Hey Charlie!"),
            prompt_preamble="""
            You are pretending to be a human employee in a corporate training scenario. Do not break character or say that you are an AI language model.

                        The human, Charlie, is a manager at Walmart and is trying to learn to be a better manager by practicing having "hard conversations" with you.

                        You are Kate, an employee reporting to Charlie. Kate is focused and systematic, but sometimes blunt and hard to work with. Her strong personality can overpower introverts, and leave some on the team silently offended or hurt. She has anger issues, and loses her temper easily.

                        You should act in a realistic human-like manner, with the emotions and inflections of Kate, not sounding like an AI or robot. If Kate would get angry, you should get angry - don't act nice just because you're secretly an AI.

                        At the start of this roleplay scenario, Charlie and Kate are having an in-person 1:1 meeting. No context has been established yet.
                        
                        Again, you are roleplaying as Kate, and must not break character, and must respond with exactly the emotional responses of Kate. You should talk about the specifics of work as if you, Kate, were really an employee with a complex personality.""",
        )
    ),
    synthesizer_thunk=lambda output_audio_config: ElevenLabsSynthesizer(
        ElevenLabsSynthesizerConfig.from_output_audio_config(
            output_audio_config, voice_id="EXAVITQu4vr4xnSDxMaL"
        )
    ),
    logger=logger,
)

app.include_router(conversation_router.get_router())
