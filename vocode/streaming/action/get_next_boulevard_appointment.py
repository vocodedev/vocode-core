import logging
from typing import Dict, Optional, Type

from pydantic import BaseModel, Field
from vocode.streaming.action.base_action import BaseAction
from vocode.streaming.models.actions import (
    ActionConfig,
    ActionInput,
    ActionOutput,
    ActionType,
)

from telephony_app.integrations.boulevard.boulevard_client import (
    retrieve_next_appointment_by_phone_number,
)

logging.basicConfig()
logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)


class GetNextBoulevardAppointmentActionConfig(
    ActionConfig, type=ActionType.GET_NEXT_BOULEVARD_APPOINTMENT
):
    phone_number: str
    timezone: str = "America/Los_Angeles"
    business_id: str
    starting_phrase: str


class GetNextBoulevardAppointmentParameters(BaseModel):
    pass


class GetNextBoulevardAppointmentResponse(BaseModel):
    appointment_info: Optional[Dict[str, str]] = Field(
        None, description="Information about the next appointment"
    )


class GetNextBoulevardAppointment(
    BaseAction[
        GetNextBoulevardAppointmentActionConfig,
        GetNextBoulevardAppointmentParameters,
        GetNextBoulevardAppointmentResponse,
    ]
):
    description: str = "Retrieve the next Boulevard appointment for a given customer"
    parameters_type: Type[GetNextBoulevardAppointmentParameters] = (
        GetNextBoulevardAppointmentParameters
    )
    response_type: Type[GetNextBoulevardAppointmentResponse] = (
        GetNextBoulevardAppointmentResponse
    )

    async def run(
        self, action_input: ActionInput[GetNextBoulevardAppointmentParameters]
    ) -> ActionOutput[GetNextBoulevardAppointmentResponse]:
        try:
            next_appointment = await retrieve_next_appointment_by_phone_number(
                self.action_config.phone_number,
                self.action_config.timezone,
                self.action_config.business_id,
            )

            if next_appointment:
                appointment_info = {
                    "appointment_id": next_appointment["id"],
                    "date_time": next_appointment["startAt"],
                    "aesthetician": next_appointment["appointmentServices"][0]["staff"][
                        "displayName"
                    ],
                    "services": ", ".join(
                        [
                            service["service"]["name"]
                            for service in next_appointment["appointmentServices"]
                        ]
                    ),
                    "location": next_appointment["location"]["name"],
                }
            else:
                appointment_info = None

            return ActionOutput(
                action_type=action_input.action_config.type,
                response=GetNextBoulevardAppointmentResponse(
                    appointment_info=appointment_info
                ),
            )
        except Exception as e:
            logger.error(
                f"An error occurred while retrieving the next appointment: {str(e)}"
            )
            return ActionOutput(
                action_type=action_input.action_config.type,
                response=GetNextBoulevardAppointmentResponse(appointment_info=None),
            )
