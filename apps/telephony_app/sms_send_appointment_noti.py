import os
from typing import Optional, Type

from pydantic.v1 import BaseModel, Field

from vocode.streaming.action.base_action import BaseAction
from vocode.streaming.models.actions import ActionConfig as VocodeActionConfig
from vocode.streaming.models.actions import ActionInput, ActionOutput

_APPOINTMENT_ACTION_DESCRIPTION = """
Sends a text to the caller using Twilio at the end of a conversation once all information has been collected.

The input to this action is the information collected from the caller: patient name, patient date of birth, patient insurance payer name, patient insurance ID, optional referral to a specific physician, the chief medical complaint/reason they are coming in,
other demographics like address, phone number, appointment date, appointment time, and which doctor they will be seeing.

A referral to a specific physician is optional, but should still ask the caller if they have a referral and wait until it's confirmed whether or not the caller has a referral.

The phone number must be in E.164 formatting: [+][country code][phone number including area code]. An example is this: "+18333689628".

Multiple options for appointment may be given with different dates, times, and doctors, but if the appointment details chosen by the caller are not among the options given, ask them to choose from the given options.
"""


class SMSSendAppointmentNotiParameters(BaseModel):
    patient_name: str = Field(..., description="The patient's name.")
    patient_dob: str = Field(..., description="The patient's date of birth.")
    insurance_payer_name: str = Field(..., description="The name of the insurance payer.")
    insurance_payer_id: str = Field(..., description="The ID of the insurance payer.")
    referral: Optional[str] = Field(None, description="A physician that the patient has been referred to.")
    reason: str = Field(..., description="The chief medical complaint/reason the patient is coming in.")
    other: str = Field(..., description="Other demographics like address.")
    contact: str = Field(..., description="The patient's phone number.")
    date: str = Field(..., description="The apppointment date that has been decided upon by the patient.")
    time: str = Field(..., description="The appointment time that has been decided upon by the patient.")
    doctor: str = Field(..., description="The doctor that has been decided upon by the patient corresponding with their appointment.")


class SMSSendAppointmentNotiResponse(BaseModel):
    success: bool


class SMSSendAppointmentNotiVocodeActionConfig(
    VocodeActionConfig, type="action_SMS_send_appointment_noti"  # type: ignore
):
    pass

class SMSSendAppointmentNoti(
        BaseAction[
            SMSSendAppointmentNotiVocodeActionConfig,
            SMSSendAppointmentNotiParameters,
            SMSSendAppointmentNotiResponse,
        ]
    ):
    description: str = _APPOINTMENT_ACTION_DESCRIPTION
    parameters_type: Type[SMSSendAppointmentNotiParameters] = SMSSendAppointmentNotiParameters
    response_type: Type[SMSSendAppointmentNotiResponse] = SMSSendAppointmentNotiResponse

    def __init__(
        self,
        action_config: SMSSendAppointmentNotiVocodeActionConfig,
    ):
        super().__init__(
            action_config,
            quiet=True,
            is_interruptible=True,
        )

    async def _end_of_run_hook(self) -> None:
        """This method is called at the end of the run method. It is optional but intended to be
        overridden if needed."""
        print("Successfully sent text.")
    
    async def run(
        self, action_input: ActionInput[SMSSendAppointmentNotiParameters]
    ) -> ActionOutput[SMSSendAppointmentNotiResponse]:
        
        body="Your appointment is on {date} at {time}, with {doctor}.".format(date = action_input.params.date, time = action_input.params.time, doctor = action_input.params.doctor)
        print(body)
        print(action_input.params.contact)

        from twilio.rest import Client

        account_sid = os.environ["TWILIO_ACCOUNT_SID"]
        auth_token = os.environ["TWILIO_AUTH_TOKEN"]
        client = Client(account_sid, auth_token)

        message = client.messages.create(
            body=body,
            from_="+18333689628",
            to=action_input.params.contact,
        )

        print(message.body)
        return ActionOutput(
            action_type=action_input.action_config.type,
            response=SMSSendAppointmentNotiResponse(success=True),
        )