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


class CheckCalendarAvailabilityParameters(BaseModel):
    day: str


class CheckCalendarAvailabilityResponse(BaseModel):
    availability: List[str]



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

    def format_for_ai(self, slot_start: datetime.datetime) -> str:
        local = slot_start.astimezone(timezone(timedelta(hours=self.action_config.business_timezone_utc_offset)))
        # date = local.strftime("%A, %B %d")  # Wednesday, June 12
        return local.strftime("%I:%M %p")  # 08:35 am
        # return date + " at " + time

    async def run(
        self, action_input: ActionInput[CheckCalendarAvailabilityParameters]
    ) -> ActionOutput[CheckCalendarAvailabilityResponse]:
        raw_availability = calculate_daily_free_intervals(
            busy_times=self.action_config.busy_times,
            start_of_day=self.action_config.start_of_day or 10,
            end_of_day=self.action_config.end_of_day or 18,
            date=action_input.params.day
        )
        availability = [self.format_for_ai(slot["start"]) for slot in raw_availability]
        logger.info(f"availability: {availability}")

        return ActionOutput(
            action_type=action_input.action_config.type,
            response=CheckCalendarAvailabilityResponse(availability=availability),
        )
