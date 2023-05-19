import os
import sys
import typing
from dotenv import load_dotenv

from tools.contacts import get_all_contacts
from tools.vocode import call_phone_number
from vocode.turn_based.synthesizer.azure_synthesizer import AzureSynthesizer
from vocode.turn_based.synthesizer.gtts_synthesizer import GTTSSynthesizer

from callback_handler import VocodeCallbackHandler
from stdout_filterer import RedactPhoneNumbers

load_dotenv()

from langchain.chat_models import ChatOpenAI
from langchain.agents import initialize_agent
from langchain.agents import AgentType

if __name__ == "__main__":
    # Redirect stdout to our custom class
    sys.stdout = typing.cast(typing.TextIO, RedactPhoneNumbers(sys.stdout))

    OBJECTIVE = (
        input("Objective: ")
        or "Find a random person in my contacts and tell them a joke"
    )
    llm = ChatOpenAI(temperature=0, model_name="gpt-4")  # type: ignore
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
