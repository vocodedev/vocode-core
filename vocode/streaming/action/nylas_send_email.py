from typing import Optional, Type
from pydantic import Field
import os
from vocode.streaming.action.respond_action import RespondAction
from vocode.streaming.models.actions import ActionInput, ActionOutput, ActionType


class NylasSendEmailActionInput(ActionInput):
    class Parameters(ActionInput.Parameters):
        recipient_email: str = Field(
            ..., description="The email address of the recipient."
        )
        body: str = Field(..., description="The body of the email.")
        subject: Optional[str] = Field(None, description="The subject of the email.")

    action_type: str = ActionType.NYLAS_SEND_EMAIL.value
    params: Parameters


class NylasSendEmailActionOutput(ActionOutput):
    class Response(ActionOutput.Response):
        success: bool

    action_type: str = ActionType.NYLAS_SEND_EMAIL.value
    response: Response


class NylasSendEmail(
    RespondAction[NylasSendEmailActionInput, NylasSendEmailActionOutput]
):
    description: str = "Sends an email using Nylas API."
    action_type: str = ActionType.NYLAS_SEND_EMAIL.value

    def run(
        self, action_input: NylasSendEmailActionInput
    ) -> NylasSendEmailActionOutput:
        from nylas import APIClient

        # Initialize the Nylas client
        nylas = APIClient(
            client_id=os.getenv("NYLAS_CLIENT_ID"),
            client_secret=os.getenv("NYLAS_CLIENT_SECRET"),
            access_token=os.getenv("NYLAS_ACCESS_TOKEN"),
        )

        # Create the email draft
        draft = nylas.drafts.create()
        draft.body = action_input.params.body

        email_subject = action_input.params.subject
        draft.subject = email_subject if email_subject else "Email from Vocode"
        draft.to = [{"email": action_input.params.recipient_email.strip()}]

        # Send the email
        draft.send()

        return NylasSendEmailActionOutput(
            response=NylasSendEmailActionOutput.Response(success=True)
        )

    @property
    def action_input_type(self) -> Type[NylasSendEmailActionInput]:
        return NylasSendEmailActionInput

    @property
    def action_output_type(self) -> Type[NylasSendEmailActionOutput]:
        return NylasSendEmailActionOutput
