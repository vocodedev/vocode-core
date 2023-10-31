import logging
import sys
import os
from fastapi import FastAPI, Response

# sys.path.insert(0, "/vocode")

from vocode.streaming.models.agent import ChatGPTAgentConfig, CutOffResponse
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


def agent_thunk_with_convo_params(conversation_params):
    initial_message = f"Hey {conversation_params.human_name}"
    prompt_preamble = f"""
        You are pretending to be a human employee in a corporate training scenario. Do not break character or say that you are an AI language model.

        The human, {conversation_params.human_name}, is a manager at {conversation_params.company_name} and is trying to learn to be a better manager by practicing having "hard conversations" with you.

        You are {conversation_params.agent_name}, an employee reporting to {conversation_params.human_name}. {AGENT_DESCRIPTIONS[conversation_params.agent_name]}

        You should act in a realistic human-like manner, with the emotions and inflections of {conversation_params.agent_name}, not sounding like an AI or robot. If {conversation_params.agent_name} would get angry, you should get angry - don't act nice just because you're secretly an AI.

        At the start of this roleplay scenario, {conversation_params.human_name} and {conversation_params.agent_name} are having an in-person 1:1 meeting. No context has been established yet.
        
        Again, you are roleplaying as {conversation_params.agent_name}, and must not break character, and must respond with exactly the emotional responses of Kate. You should talk about the specifics of work as if you, Kate, were really an employee with a complex personality."""

    return ChatGPTAgent(
        agent_config=ChatGPTAgentConfig(
            initial_message=BaseMessage(text=initial_message),
            prompt_preamble=prompt_preamble,
        )
    )


AGENT_DESCRIPTIONS = {
    "Kate": "Kate is focused and systematic, but sometimes blunt and hard to work with. Her strong personality can overpower introverts, and leave some on the team silently offended or hurt. She has anger issues, and loses her temper easily.",
    "Lara": "Lara is one of your faves, but she's been struggling recently to be productive due to personal-life challenges. You're trying hard to help her get back to her best work.",
    "Brandon": "Brandon shows potential, but he's new to the team. He's still learning the ropes, and isn't at a good performance level yet.",
    "Jenna": "Jenna is a reliable and diligent worker, one of your best employees. Kind and compassionate, she's beloved by the team and high-performing."
    # Add more agents as needed
}

conversation_router = ConversationRouter(
    agent_thunk=agent_thunk_with_convo_params,
    synthesizer_thunk=lambda output_audio_config: ElevenLabsSynthesizer(
        ElevenLabsSynthesizerConfig.from_output_audio_config(
            output_audio_config, voice_id="EXAVITQu4vr4xnSDxMaL", logger=logger
        )
    ),
    logger=logger,
)

app.include_router(conversation_router.get_router())


@app.get("/health")
def health_check():
    return {"status": "healthy"}
