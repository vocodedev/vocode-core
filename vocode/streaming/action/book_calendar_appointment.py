import asyncio
import logging
from telephony_app.utils.date_parser import parse_natural_language_date
from telephony_app.integrations.oauth import OauthCredentials
from telephony_app.integrations.gcal.gcal_helpers import GcalAdapter
import datetime
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

logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)

class BookCalendarAppointmentActionConfig(ActionConfig, type=ActionType.CHECK_CALENDAR_AVAILABILITY):
    credentials: OauthCredentials
    guest_phone_number: str
    host_email: str
    host_name: str
    appointment_length_minutes: int


class BookCalendarAppointmentParameters(BaseModel):
    guest_name: Optional[str]
    guest_email: Optional[str]
    description: str
    date: str

class BookCalendarAppointmentResponse(BaseModel):
    succeeded: bool


def book_appointment(credentials: OauthCredentials):
    with GcalAdapter(credentials) as gcal:
        gcal.events().insert

class BookCalendarAppointment(BaseAction[BookCalendarAppointmentActionConfig, BookCalendarAppointmentParameters, BookCalendarAppointmentResponse]):
    description: str = (
        "Books an appointment on the calendar"
    )
    parameters_type: Type[BookCalendarAppointmentParameters] = BookCalendarAppointmentParameters
    response_type: Type[BookCalendarAppointmentResponse] = BookCalendarAppointmentResponse

    def book_appointment(self, action_input: ActionInput[BookCalendarAppointmentParameters]):
        with GcalAdapter(self.action_config.credentials) as gcal:
            start_time = parse_natural_language_date(action_input.params.date) 
            duration = datetime.timedelta(minutes=self.action_config.appointment_length_minutes)
            response = gcal.events().insert("primary", {
                "attendees": [
                    {
                        "displayName":  action_input.params.guest_name or "unnamed caller",
                        "email": action_input.params.guest_email or "noemailprovided@gmail.com",
                        "comment": self.action_config.guest_phone_number,
                        "responseStatus": "needsAction"
                    },
                    {
                        "displayName": self.action_config.host_name,
                        "email": self.action_config.host_email,
                        "responseStatus": "needsAction",
                        "organizer": True
                    }
                ],
                "description": action_input.params.description,
                "summary": "Appointment",
                "start": {
                    "dateTime": start_time.isoformat()
                },
                "end": {
                    "dateTime": (start_time + duration).isoformat()
                }
            })
            return True

    async def run(
        self, action_input: ActionInput[BookCalendarAppointmentParameters]
    ) -> ActionOutput[BookCalendarAppointmentResponse]:
        loop = asyncio.get_event_loop()
        success = await loop.run_in_executor(None, self.book_appointment, action_input) 

        return ActionOutput(
            action_type=action_input.action_config.type,
            response=BookCalendarAppointmentResponse(success),
        )
