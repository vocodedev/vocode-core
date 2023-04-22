import os
from dotenv import load_dotenv

from tools.contacts import get_all_contacts
from tools.vocode import call_phone_number
from callback_handler import VocodeCallbackHandler
from vocode.turn_based.synthesizer.azure_synthesizer import AzureSynthesizer
from vocode.turn_based.synthesizer.gtts_synthesizer import GTTSSynthesizer

load_dotenv()

from langchain.chat_models import ChatOpenAI
from langchain.agents import initialize_agent
from langchain.agents import AgentType
from langchain.callbacks.base import CallbackManager

if __name__ == "__main__":
    OBJECTIVE = input("Objective: ") or "Find a random person in my contacts and tell them a joke"
    llm = ChatOpenAI(temperature=0, model_name="gpt-4")
    # Logging of LLMChains
    verbose = True
    agent = initialize_agent(
        tools=[get_all_contacts, call_phone_number],
        llm=llm,
        agent=AgentType.CHAT_ZERO_SHOT_REACT_DESCRIPTION,
        verbose=verbose,
    )
    agent.callback_manager.add_handler(
        VocodeCallbackHandler(
            AzureSynthesizer(voice_name="en-US-SteffanNeural"),
        )
    )
    agent.run(OBJECTIVE)
