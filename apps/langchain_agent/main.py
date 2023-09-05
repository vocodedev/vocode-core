import os
import sys
import typing
from dotenv import load_dotenv

from tools.contacts import get_all_contacts
from tools.vocode import call_phone_number
from tools.word_of_the_day import word_of_the_day
from vocode.turn_based.synthesizer.azure_synthesizer import AzureSynthesizer
from vocode.turn_based.synthesizer.gtts_synthesizer import GTTSSynthesizer
from langchain.memory import ConversationBufferMemory


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
    memory = ConversationBufferMemory(memory_key="chat_history", return_messages=True)
    # Logging of LLMChains
    verbose = True
    agent = initialize_agent(
        tools=[get_all_contacts, call_phone_number, word_of_the_day],
        llm=llm,
        agent=AgentType.CHAT_CONVERSATIONAL_REACT_DESCRIPTION,
        verbose=verbose,
        memory=memory,
    )
    agent.run(OBJECTIVE)
