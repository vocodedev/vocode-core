from vocode.streaming.action.base_action import BaseAction

from vocode.streaming.models.actions import ActionConfig
from vocode.streaming.action.hangup_call import HangUpCall, HangUpCallActionConfig
from vocode.streaming.action.transfer_call import TransferCall, TransferCallActionConfig
from vocode.streaming.action.search_online import SearchOnline, SearchOnlineActionConfig
from vocode.streaming.action.create_agent import CreateAgent, CreateAgentActionConfig
from vocode.streaming.action.search_documents import (
    SearchDocuments,
    SearchDocumentsActionConfig,
)
from vocode.streaming.action.send_text import SendText, SendTextActionConfig
from vocode.streaming.action.get_train import GetTrain, GetTrainActionConfig
from vocode.streaming.action.use_calendly import UseCalendly, CalendlyActionConfig
from vocode.streaming.action.send_hello_sugar_directions import (
    SendHelloSugarDirections,
    SendHelloSugarDirectionsActionConfig,
)
from vocode.streaming.action.send_hello_sugar_booking_instructions import (
    SendHelloSugarBookingInstructions,
    SendHelloSugarBookingInstructionsActionConfig,
)
from vocode.streaming.action.check_calendar_availability import (
    CheckCalendarAvailability,
    CheckCalendarAvailabilityActionConfig,
)
from vocode.streaming.action.book_calendar_appointment import (
    BookCalendarAppointment,
    BookCalendarAppointmentActionConfig,
)

# use_instructions
from vocode.streaming.action.retrieve_instructions import (
    RetrieveInstructions,
    RetrieveInstructionsActionConfig,
)
from vocode.streaming.action.nylas_send_email import (
    SendEmail,
    NylasSendEmailActionConfig,
)


class ActionFactory:
    def create_action(self, action_config: ActionConfig) -> BaseAction:
        if isinstance(action_config, NylasSendEmailActionConfig):
            return SendEmail(action_config)
        elif isinstance(action_config, TransferCallActionConfig):
            return TransferCall(action_config)
        elif isinstance(action_config, HangUpCallActionConfig):
            return HangUpCall(action_config)
        elif isinstance(action_config, GetTrainActionConfig):
            return GetTrain(action_config)
        elif isinstance(action_config, SearchOnlineActionConfig):
            return SearchOnline(action_config)
        elif isinstance(action_config, SendTextActionConfig):
            return SendText(action_config)
        elif isinstance(action_config, CalendlyActionConfig):
            return UseCalendly(action_config)
        elif isinstance(action_config, RetrieveInstructionsActionConfig):
            return RetrieveInstructions(action_config)
        elif isinstance(action_config, SendHelloSugarDirectionsActionConfig):
            return SendHelloSugarDirections(action_config)
        elif isinstance(action_config, SendHelloSugarBookingInstructionsActionConfig):
            return SendHelloSugarBookingInstructions(action_config)
        elif isinstance(action_config, CheckCalendarAvailabilityActionConfig):
            return CheckCalendarAvailability(action_config)
        elif isinstance(action_config, BookCalendarAppointmentActionConfig):
            return CheckCalendarAvailability(action_config)
        elif isinstance(action_config, CreateAgentActionConfig):
            return CreateAgent(action_config)
        elif isinstance(action_config, SearchDocumentsActionConfig):
            return SearchDocuments(action_config)
        else:
            raise Exception("Invalid action type")
