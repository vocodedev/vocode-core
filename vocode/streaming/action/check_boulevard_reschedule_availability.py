import logging
import os
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Type

import pytz
from dateutil import parser as date_parser
from pydantic import BaseModel
from vocode.streaming.action.base_action import BaseAction
from vocode.streaming.models.actions import (
    ActionConfig,
    ActionInput,
    ActionOutput,
    ActionType,
)

from telephony_app.integrations.boulevard.boulevard_client import (
    get_app_credentials,
    get_available_reschedule_times,
    get_time_slot,
    parse_times,
)

logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)


class CheckBoulevardRescheduleAvailabilityActionConfig(
    ActionConfig, type=ActionType.CHECK_BOULEVARD_RESCHEDULE_AVAILABILITY
):
    business_id: str
    timezone: str = "America/Los_Angeles"
    starting_phrase: str


class CheckBoulevardRescheduleAvailabilityParameters(BaseModel):
    days_in_advance: int = 7
    appointment_id: str


class CheckBoulevardRescheduleAvailabilityResponse(BaseModel):
    message: str


class CheckBoulevardRescheduleAvailability(
    BaseAction[
        CheckBoulevardRescheduleAvailabilityActionConfig,
        CheckBoulevardRescheduleAvailabilityParameters,
        CheckBoulevardRescheduleAvailabilityResponse,
    ]
):
    description: str = """Checks for available reschedule times on Boulevard for the specified number of days in advance. 
    NOTE: This action is currently only supported for the next appointment for a given phone number."""

    parameters_type: Type[CheckBoulevardRescheduleAvailabilityParameters] = (
        CheckBoulevardRescheduleAvailabilityParameters
    )
    response_type: Type[CheckBoulevardRescheduleAvailabilityResponse] = (
        CheckBoulevardRescheduleAvailabilityResponse
    )

    async def run(
        self, action_input: ActionInput[CheckBoulevardRescheduleAvailabilityParameters]
    ) -> ActionOutput[CheckBoulevardRescheduleAvailabilityResponse]:
        try:
            if not action_input.params.appointment_id:
                return ActionOutput(
                    action_type=action_input.action_config.type,
                    response=CheckBoulevardRescheduleAvailabilityResponse(
                        message="I'm sorry, but there's no appointment scheduled that we can reschedule."
                    ),
                )

            timezone = pytz.timezone(self.action_config.timezone)
            start_date = datetime.now(timezone).date()
            end_date = start_date + timedelta(days=action_input.params.days_in_advance)
            availability: Dict[str, Dict[str, Dict[str, str]]] = {}
            memories = []
            slot_counter = 1

            for i in range(action_input.params.days_in_advance):
                current_date = start_date + timedelta(days=i)
                formatted_date = current_date.strftime("%Y-%m-%d")
                available_times = await get_available_reschedule_times(
                    appointment_id=action_input.params.appointment_id,
                    business_id=self.action_config.business_id,
                    date=formatted_date,
                    env=os.getenv(key="ENV", default="dev"),
                )

                if available_times:
                    parsed_times = parse_times(available_times)
                    time_slots = {
                        time: get_time_slot(available_times, time)
                        for time in parsed_times
                    }
                    availability[formatted_date] = time_slots

            if not availability:
                return ActionOutput(
                    action_type=action_input.action_config.type,
                    response=CheckBoulevardRescheduleAvailabilityResponse(
                        message=f"There are no available times for rescheduling in the next {action_input.params.days_in_advance} days."
                    ),
                )

            num_slots = len(availability)
            num_slots_label = (
                f"We only found 1 timeslot"
                if num_slots == 1
                else f"We found {num_slots} timeslots"
            )
            message = f"{num_slots_label}. Here are the available time(s) for rescheduling the appointment in the next {action_input.params.days_in_advance} days (all times are in {self.action_config.timezone}):\n"

            for date, times in availability.items():
                formatted_date = (
                    datetime.strptime(date, "%Y-%m-%d")
                    .replace(tzinfo=timezone)
                    .strftime("%A, %B %d")
                )
                message += f"\nFor {formatted_date}:\n"
                if times:
                    for time, slot in times.items():
                        message += f"  - slot_{slot_counter}: {time} (ID: '{slot.get('bookableTimeId')}')\n"
                        memories.append(
                            {f"slot_{slot_counter}": slot.get("bookableTimeId")}
                        )
                        slot_counter += 1
                else:
                    message += "  [Alert] There are no available times on this day.\n"

            return ActionOutput(
                action_type=action_input.action_config.type,
                response=CheckBoulevardRescheduleAvailabilityResponse(message=message),
                memories=memories,
            )
        except Exception as e:
            # log the trace
            logger.error(
                f"An error occurred while checking reschedule availability: {str(e)}"
            )
            return ActionOutput(
                action_type=action_input.action_config.type,
                response=CheckBoulevardRescheduleAvailabilityResponse(
                    message="I apologize, but I encountered an error while checking available times. Please try again later."
                ),
            )
