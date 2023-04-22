import os
from dotenv import load_dotenv

from tools.contacts import get_all_contacts
from tools.vocode import call_phone_number

load_dotenv()

from langchain.chat_models import ChatOpenAI
from langchain.agents import initialize_agent
from langchain.agents import AgentType

if __name__ == "__main__":
    OBJECTIVE = "Find a random person in my contacts and tell them a joke"
    llm = ChatOpenAI(temperature=0, model_name="gpt-4")
    # Logging of LLMChains
    verbose = True
    agent = initialize_agent(
        tools=[get_all_contacts, call_phone_number],
        llm=llm,
        agent=AgentType.CHAT_ZERO_SHOT_REACT_DESCRIPTION,
        verbose=verbose,
    )
    agent.run(OBJECTIVE)
