from typing import List, Optional

from custom_action_factory import MyCustomActionFactory
from sms_send_appointment_noti import SMSSendAppointmentNotiVocodeActionConfig

from vocode.streaming.agent.chat_gpt_agent import ChatGPTAgent
from vocode.streaming.models.actions import ActionConfig
from vocode.streaming.models.agent import ChatGPTAgentConfig


class CustomAgentConfig(ChatGPTAgentConfig, type="agent_custom"):
    actions: Optional[List[ActionConfig]] = [SMSSendAppointmentNotiVocodeActionConfig]
    pass

class CustomAgent(ChatGPTAgent[CustomAgentConfig]):
    def __init__(
            self,
            agent_config: CustomAgentConfig,
            action_factory: MyCustomActionFactory,
    ):
        super().__init__(agent_config, action_factory=action_factory)
