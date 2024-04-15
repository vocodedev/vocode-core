from ast import List
import logging
from telephony_app.utils.date_parser import get_availability_for_day
from datetime import datetime
from dateutil import tz
from typing import Optional, Type, TypedDict
from pydantic import BaseModel, Field
from vocode.streaming.models.actions import (
    ActionConfig,
    ActionInput,
    ActionOutput,
    ActionType,
)
from vocode.streaming.action.base_action import BaseAction
import datetime

class OauthCredentials(TypedDict):
    access_token: str
    refresh_token: str
    token_uri: str
    client_id: str
    client_secret: str
    scopes: Optional[List[str]]
    scope: Optional[str]

class GcalInterval(TypedDict):
    start: str # UTC ISO
    end: str # UTC ISO

logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)


class BookGcalAppointmentActionConfig(ActionConfig, type=ActionType.CHECK_GCAL_AVAILABILITY):
    credentials: OauthCredentials
    all_availability: List[GcalInterval]


class BookGcalAppointmentParameters(BaseModel):
    day: str

class BookGcalAppointmentResponse(BaseModel):
    availability: List[str]


# assumes UTC, i.e. 2024-04-11T16:00:00Z
def natural_lang_date(iso: str) -> str:
    from_zone = tz.gettz('UTC')
    to_zone = tz.gettz('America/New_York')

    utc = datetime.datetime.strptime(iso, '%Y-%m-%dT%H:%M:%S')
    utc = utc.replace(tzinfo=from_zone)
    local = utc.astimezone(to_zone)
    date = local.strftime("%A, %B %d") # Wednesday, June 12
    time = local.strftime("%I:%M %p") # 08:35 am
    return date + " at " + time

class BookGcalAppointment(BaseAction[BookGcalAppointmentActionConfig, BookGcalAppointmentParameters, BookGcalAppointmentResponse]):
    description: str = (
        "Retrieves google calendar availability on a specific day/time"
    )
    parameters_type: Type[BookGcalAppointmentParameters] = BookGcalAppointmentParameters
    response_type: Type[BookGcalAppointmentResponse] = BookGcalAppointmentResponse

    async def run(
        self, action_input: ActionInput[BookGcalAppointmentParameters]
    ) -> ActionOutput[BookGcalAppointmentResponse]:
        raw_availability = get_availability_for_day(self.action_config.all_availability, action_input.params.day)
        availability = [natural_lang_date(slot["start"]) for slot in raw_availability]

        return ActionOutput(
            action_type=action_input.action_config.type,
            response=BookGcalAppointmentResponse(vailability=availability),
        )