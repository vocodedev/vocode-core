import logging
import os
from telephony_app.utils.date_parser import parse_natural_language_date
from telephony_app.integrations.oauth import OauthCredentials
from telephony_app.integrations.gcal.gcal_helpers import get_google_scopes
from aiogoogle import Aiogoogle
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

class BookCalendarAppointmentActionConfig(ActionConfig, type=ActionType.BOOK_CALENDAR_APPOINTMENT):
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


class BookCalendarAppointment(BaseAction[BookCalendarAppointmentActionConfig, BookCalendarAppointmentParameters, BookCalendarAppointmentResponse]):
    description: str = (
        "Books an appointment on the calendar"
    )
    parameters_type: Type[BookCalendarAppointmentParameters] = BookCalendarAppointmentParameters
    response_type: Type[BookCalendarAppointmentResponse] = BookCalendarAppointmentResponse

    async def book_appointment(self, action_input: ActionInput[BookCalendarAppointmentParameters]):
        aiogoogle_creds = {
            "token": self.action_config.params.credentials.get("access_token"),
            "refresh_token": self.action_config.params.credentials.get("refresh_token"),
            "scopes": get_google_scopes(oauth_credentials=self.action_config.params.credentials),
            "token_uri": "https://oauth2.googleapis.com/token",
            "client_id": os.getenv("GOOGLE_OAUTH_CLIENT_ID"),
            "client_secret": os.getenv("GOOGLE_OAUTH_CLIENT_SECRET"),
        }
        async with Aiogoogle(user_creds=aiogoogle_creds) as aiogoogle:
            calendar_v3 = await aiogoogle.discover('calendar', 'v3')
            start_time = parse_natural_language_date(action_input.params.date) 
            duration = datetime.timedelta(minutes=self.action_config.appointment_length_minutes)
            response = await aiogoogle.as_user(
                calendar_v3.events().insert("primary", {
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
            )
            logger.info(f"cal booking response: {response}")
            return True

    async def run(
        self, action_input: ActionInput[BookCalendarAppointmentParameters]
    ) -> ActionOutput[BookCalendarAppointmentResponse]:
        success = await self.book_appointment(action_input=action_input) 

        return ActionOutput(
            action_type=action_input.action_config.type,
            response=BookCalendarAppointmentResponse(success),
        )
