import logging

from vocode import getenv
import httpx
from typing import Type
from pydantic import BaseModel, Field

from vocode.streaming.action.base_action import BaseAction
from vocode.streaming.models.actions import (
    ActionConfig,
    ActionInput,
    ActionOutput,
    ActionType,
)
from enum import Enum
import requests
import json

logging.basicConfig()
logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)


class CalendlyActionType(Enum):
    LIST_EVENTS = "list_events"
    CANCEL_EVENT = "cancel_event"


class CalendlyActionConfig(ActionConfig, type=ActionType.USE_CALENDLY):
    pass


class CalendlyParameters(BaseModel):
    api_key: str = Field(..., description="API key for Calendly")
    action_type: CalendlyActionType = Field(
        ..., description="The type of Calendly action to perform"
    )
    args: dict = Field(
        {}, description="Arguments required for the specific Calendly action"
    )


class CalendlyResponse(BaseModel):
    action_type: CalendlyActionType = Field(
        ..., description="The type of Calendly action that was performed"
    )
    result: str = Field(..., description="The result of the Calendly action")


class UseCalendly(
    BaseAction[CalendlyActionConfig, CalendlyParameters, CalendlyResponse]
):
    description: str = (
        "Performs actions related to Calendly based on the provided parameters"
    )
    parameters_type: Type[CalendlyParameters] = CalendlyParameters
    response_type: Type[CalendlyResponse] = CalendlyResponse

    base_url = "https://api.calendly.com/"
    userid = None
    scheduling_url = None

    @classmethod
    def update_attributes(cls, api_key):
        cls.headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {api_key}",
        }
        cls.set_userid(api_key)

    @classmethod
    def set_userid(cls, api_key):
        url = cls.base_url + "users/me"
        api_key = getenv(api_key)
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {api_key}",
        }
        response = requests.get(url, headers=headers)
        logger.debug(f"Response: {response.text}")
        cls.scheduling_url = json.loads(response.text)["resource"]["scheduling_url"]
        cls.userid = json.loads(response.text)["resource"]["uri"]

    @classmethod
    def list_events(cls, api_key, args):
        url = cls.base_url + "scheduled_events"
        args["user"] = cls.userid
        api_key = getenv(api_key)
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {api_key}",
        }
        response = requests.get(url, params=args, headers=headers)
        # add the scheduling url to the response
        response = json.loads(response.text)
        response["scheduling_url"] = cls.scheduling_url
        events = response.get("collection", [])
        if events:
            pretty_events = "\n".join(
                [f"- {event['name']} at {event['start_time']}" for event in events]
            )
        else:
            pretty_events = "No scheduled events. The schedule is open."
        scheduling_link = response.get(
            "scheduling_url", "No scheduling link available."
        )
        pretty_response = (
            f"Scheduled Events:\n{pretty_events}\n\nBooking Link:\n{scheduling_link}"
        )
        response = json.dumps({"details": pretty_response}, indent=4)
        return response

    async def run(
        self, action_input: ActionInput[CalendlyParameters]
    ) -> ActionOutput[CalendlyResponse]:
        api_key = action_input.params.api_key
        action_type = action_input.params.action_type
        args = action_input.params.args

        # Update attributes with the provided API key
        self.update_attributes(api_key)

        try:
            result = ""
            if action_type == CalendlyActionType.LIST_EVENTS:
                result = self.list_events(api_key, args)
            elif action_type == CalendlyActionType.CANCEL_EVENT:
                result = self.cancel_event(api_key, args)
            response = CalendlyResponse(action_type=action_type, result=result)
        except Exception as e:
            response = CalendlyResponse(action_type=action_type, result=str(e))

        return ActionOutput(
            action_type=action_input.action_config.type,
            response=response,
        )
