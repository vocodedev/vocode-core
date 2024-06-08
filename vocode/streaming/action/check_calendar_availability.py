import logging
from telephony_app.utils.date_parser import (
    calculate_daily_free_intervals,
    Interval,
    parse_natural_language_date,
    parse_natural_language_time,
)
from telephony_app.integrations.oauth import OauthCredentials
from datetime import datetime, time, timezone, timedelta
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
    time: str


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
            start_of_day=self.action_config.start_of_day or 9,
            end_of_day=self.action_config.end_of_day or 17,
            date=action_input.params.day,
            tz=tz,
            appointment_length_minutes=self.action_config.appointment_length_minutes,
        )
        if (
            not action_input.params.time
            or action_input.params.time == ""
            or action_input.params.time == "None"
        ):
            return ActionOutput(
                action_type=action_input.action_config.type,
                response=CheckCalendarAvailabilityResponse(
                    availability="Error: Please provide a time to check availability"
                ),
            )
        try:
            # Convert the UTC offset to a timezone string and parse the provided day into a date object
            timezone_str = (
                f"UTC{action_input.action_config.business_timezone_utc_offset:+03d}:00"
            )
            parsed_date = parse_natural_language_date(
                action_input.params.day,
                timezone_str,
            )
            # Parse the provided time into a time object
            parsed_time = parse_natural_language_time(action_input.params.time)
            # Combine the parsed date and time into a datetime object
            start_time = datetime.datetime.combine(parsed_date, parsed_time.time())
            start_time = start_time.replace(
                tzinfo=timezone(
                    timedelta(hours=self.action_config.business_timezone_utc_offset)
                )
            )
        except Exception as e:
            logger.exception(
                f"Error parsing the provided date and time: {action_input.params.day} {action_input.params.time}"
            )
            return ActionOutput(
                action_type=action_input.action_config.type,
                response=CheckCalendarAvailabilityResponse(
                    availability="Formatting Error: Please provide a valid date and time to check availability"
                ),
            )

        # Convert the start_time to Unix timestamp for comparison
        start_time_unix = start_time.timestamp()

        # Format the raw availability into a natural language, numbered list
        formatted_availability = [
            f"Block {index + 1}: Available from {self.format_for_ai(interval['start'])} to {self.format_for_ai(interval['end'] - datetime.timedelta(minutes=self.action_config.appointment_length_minutes))}"
            for index, interval in enumerate(raw_availability)
        ]
        schedule_message = (
            f"The schedule on {action_input.params.day} is:\n\n{formatted_availability}"
        )

        # Check if the start time is within an available block
        min_slot_duration = timedelta(
            minutes=self.action_config.appointment_length_minutes
        )
        valid_time = False
        unavailability_reason = ""
        for interval in raw_availability:
            interval_start_unix = interval["start"].timestamp()
            interval_end_unix = interval["end"].timestamp()
            if interval_start_unix <= start_time_unix < interval_end_unix:
                if (
                    interval_end_unix - start_time_unix
                    >= min_slot_duration.total_seconds()
                ):
                    valid_time = True
                    break
                else:
                    unavailability_reason = f"the availability block is too short to fit a {self.action_config.appointment_length_minutes}-minute appointment before the next scheduled event."
                    break
            elif start_time_unix < interval_start_unix:
                unavailability_reason = f"the requested start time is before the next available block starting at {self.format_for_ai(interval['start'])}."
                break
            elif start_time_unix >= interval_end_unix:
                unavailability_reason = f"the requested start time is after the current available block ending at {self.format_for_ai(interval['end'])}."
                # Do not break here to allow checking against subsequent intervals

        if valid_time:
            validation_message = f"\nThe start time of {self.format_for_ai(start_time)} is a valid time for scheduling."
        else:
            validation_message = f"\nThe start time of {self.format_for_ai(start_time)} is unavailable for scheduling because {unavailability_reason}"

        formatted_availability = schedule_message + validation_message

        return ActionOutput(
            action_type=action_input.action_config.type,
            response=CheckCalendarAvailabilityResponse(
                availability=formatted_availability
            ),
        )
