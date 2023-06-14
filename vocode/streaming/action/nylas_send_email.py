import json
from typing import Any, Dict, Optional
from vocode.streaming.action.base_action import BaseAction
import os
from vocode.streaming.models.actions import ActionInput, ActionOutput, ActionType


class NylasSendEmailActionInput(ActionInput):
    class Parameters(ActionInput.Parameters):
        recipient_email: str
        body: str
        subject: Optional[str]

    action_type: str = ActionType.NYLAS_SEND_EMAIL.value
    params: Parameters


class NylasSendEmailActionOutput(ActionOutput):
    class Response(ActionOutput.Response):
        success: bool

    action_type: str = ActionType.NYLAS_SEND_EMAIL.value
    response: Response


class NylasSendEmail(BaseAction[NylasSendEmailActionInput, NylasSendEmailActionOutput]):
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

    def get_openai_function(self):
        return {
            "name": ActionType.NYLAS_SEND_EMAIL.value,
            "description": "Sends an email using Nylas API.",
            "parameters": {
                "type": "object",
                "properties": {
                    "recipient_email": {
                        "type": "string",
                        "description": "The email address of the recipient.",
                    },
                    "body": {
                        "type": "string",
                        "description": "The body of the email.",
                    },
                    "subject": {
                        "type": "string",
                        "description": "The subject of the email.",
                    },
                },
                "required": ["recipient_email", "body"],
            },
        }

    def create_action_input(
        self, conversation_id: str, params: Dict[str, Any]
    ) -> NylasSendEmailActionInput:
        return NylasSendEmailActionInput(
            conversation_id=conversation_id,
            params=NylasSendEmailActionInput.Parameters(**params),
        )
