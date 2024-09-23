import logging
import os
from datetime import datetime
from typing import Optional, Type

from pydantic import BaseModel, Field
from vocode.streaming.action.base_action import BaseAction
from vocode.streaming.models.actions import (
    ActionConfig,
    ActionInput,
    ActionOutput,
    ActionType,
)

from telephony_app.integrations.boulevard.boulevard_client import (
    CURRENT_BOULEVARD_CREDENTIALS,
    reschedule_appointment,
)

logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)


class RescheduleBoulevardAppointmentActionConfig(
    ActionConfig, type=ActionType.RESCHEDULE_BOULEVARD_APPOINTMENT
):
    business_id: str
    starting_phrase: str


class RescheduleBoulevardAppointmentParameters(BaseModel):
    selected_time_id: str
    appointment_id: str


class RescheduleBoulevardAppointmentResponse(BaseModel):
    succeeded: bool
    new_appointment_time: Optional[str] = None


class RescheduleBoulevardAppointment(
    BaseAction[
        RescheduleBoulevardAppointmentActionConfig,
        RescheduleBoulevardAppointmentParameters,
        RescheduleBoulevardAppointmentResponse,
    ]
):
    description: str = """Reschedules an appointment on Boulevard.
    Note: this action only currently supports rescheduling for the next appointment."""
    parameters_type: Type[RescheduleBoulevardAppointmentParameters] = (
        RescheduleBoulevardAppointmentParameters
    )
    response_type: Type[RescheduleBoulevardAppointmentResponse] = (
        RescheduleBoulevardAppointmentResponse
    )

    async def run(
        self, action_input: ActionInput[RescheduleBoulevardAppointmentParameters]
    ) -> ActionOutput[RescheduleBoulevardAppointmentResponse]:
        if not action_input.params.appointment_id:
            logger.error("No upcoming appointment found.")
            return ActionOutput(
                action_type=action_input.action_config.type,
                response=RescheduleBoulevardAppointmentResponse(succeeded=False),
            )

        response = await reschedule_appointment(
            appointment_id=action_input.params.appointment_id,
            bookable_time_id=action_input.params.selected_time_id,
            business_id=CURRENT_BOULEVARD_CREDENTIALS.business_id,
            env=os.getenv(key="ENV", default="dev"),
            send_notification=True,
        )

        if (
            response
            and response.get("data")
            and response["data"].get("appointmentReschedule")
        ):
            new_appointment = response["data"]["appointmentReschedule"]["appointment"]
            logger.info(
                f"Appointment rescheduled successfully. New appointment ID: {new_appointment['id']}"
            )
            return ActionOutput(
                action_type=action_input.action_config.type,
                response=RescheduleBoulevardAppointmentResponse(
                    succeeded=True,
                    new_appointment_time=action_input.params.selected_time_id,
                ),
            )
        else:
            logger.error("Failed to reschedule the appointment.")
            return ActionOutput(
                action_type=action_input.action_config.type,
                response=RescheduleBoulevardAppointmentResponse(succeeded=False),
            )
