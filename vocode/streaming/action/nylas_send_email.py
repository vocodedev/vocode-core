import json
from vocode.streaming.action.base_action import BaseAction
import os
from vocode.streaming.models.actions import NylasSendEmailActionOutput


class NylasSendEmail(BaseAction[NylasSendEmailActionOutput]):
    def run(self, params: str) -> NylasSendEmailActionOutput:
        """Sends an email using Nylas API.
        The input to this action is a pipe separated list of the recipient email, email body, optional subject. But always include
        the pipe character even if the subject or message IDs are not included and just leave it blank.
        The subject should only be included if it is a new email thread.
        If there is no message id, the email will be sent as a new email. Otherwise, it will be sent as a reply to the given message. Make sure to include the previous message_id
        if you are replying to an email.

        For example, `recipient@example.com|Hello, this is the email body.|this is the subject` would send an email to recipient@example.com with the provided body and subject.
        """
        recipient_email, email_body, email_subject = params.split("|")

        from nylas import APIClient

        # Initialize the Nylas client
        nylas = APIClient(
            client_id=os.getenv("NYLAS_CLIENT_ID"),
            client_secret=os.getenv("NYLAS_CLIENT_SECRET"),
            access_token=os.getenv("NYLAS_ACCESS_TOKEN"),
        )

        # Create the email draft
        draft = nylas.drafts.create()
        draft.body = email_body

        draft.subject = (
            email_subject.strip() if email_subject.strip() else "Email from Vocode"
        )
        draft.to = [{"email": recipient_email.strip()}]

        # Send the email
        draft.send()

        return NylasSendEmailActionOutput(response=json.dumps({"success": True}))
