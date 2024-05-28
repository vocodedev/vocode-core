import logging
from telephony_app.utils.date_parser import calculate_daily_free_intervals, Interval
from telephony_app.integrations.oauth import OauthCredentials
from datetime import datetime, timezone, timedelta
from typing import List, Optional, Type, TypedDict
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


class CheckCalendarAvailabilityActionConfig(
    ActionConfig, type=ActionType.CHECK_CALENDAR_AVAILABILITY
):
    credentials: OauthCredentials
    busy_times: List[Interval]
    starting_phrase: str
    start_of_day: int
    end_of_day: int
    business_timezone_utc_offset: int
    appointment_length_minutes: int


class CheckCalendarAvailabilityParameters(BaseModel):
    day: str


class CheckCalendarAvailabilityResponse(BaseModel):
    availability: str


class CheckCalendarAvailability(
    BaseAction[
        CheckCalendarAvailabilityActionConfig,
        CheckCalendarAvailabilityParameters,
        CheckCalendarAvailabilityResponse,
    ]
):
    description: str = "Retrieves google calendar availability on a specific day/time"
    parameters_type: Type[CheckCalendarAvailabilityParameters] = (
        CheckCalendarAvailabilityParameters
    )
    response_type: Type[CheckCalendarAvailabilityResponse] = (
        CheckCalendarAvailabilityResponse
    )

    def format_for_ai(self, date: datetime.datetime) -> str:
        local = date.astimezone(
            timezone(timedelta(hours=self.action_config.business_timezone_utc_offset))
        )
        # date = local.strftime("%A, %B %d")  # Wednesday, June 12
        return local.strftime("%I:%M %p")  # 08:35 am
        # return date + " at " + time

    async def run(
        self, action_input: ActionInput[CheckCalendarAvailabilityParameters]
    ) -> ActionOutput[CheckCalendarAvailabilityResponse]:
        # god help us
        tz = "PDT"
        if self.action_config.business_timezone_utc_offset > -6:
            tz = "EDT"

        raw_availability = calculate_daily_free_intervals(
            busy_times=self.action_config.busy_times,
            start_of_day=self.action_config.start_of_day or 10,
            end_of_day=self.action_config.end_of_day or 18,
            date=action_input.params.day,
            tz=tz,
            appointment_length_minutes=self.action_config.appointment_length_minutes,
        )

        # Format the raw availability into a natural language, numbered list
        formatted_availability = [
            f"Block {index + 1}: Available from {self.format_for_ai(interval['start'])} to {self.format_for_ai(interval['end']) - self.action_config.appointment_length_minutes}"
            for index, interval in enumerate(raw_availability)
        ]
        formatted_availability = "\n".join(formatted_availability)
        formatted_availability = (
            f"The schedule on {action_input.params.day} is:\n\n{formatted_availability}"
        )
        formatted_availability = (
            formatted_availability
            + "\n"
            + f"When scheduling, events are typically {self.action_config.appointment_length_minutes} minutes long and must fit within an available block."
        )

        return ActionOutput(
            action_type=action_input.action_config.type,
            response=CheckCalendarAvailabilityResponse(
                availability=formatted_availability
            ),
        )
