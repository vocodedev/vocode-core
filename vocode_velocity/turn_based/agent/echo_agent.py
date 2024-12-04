from vocode.turn_based.agent.base_agent import BaseAgent


class EchoAgent(BaseAgent):
    def respond(self, human_input: str):
        return human_input
