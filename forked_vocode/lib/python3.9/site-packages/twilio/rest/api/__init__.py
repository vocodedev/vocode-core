from warnings import warn

from twilio.rest.api.ApiBase import ApiBase
from twilio.rest.api.v2010.account import AccountContext, AccountList
from twilio.rest.api.v2010.account.address import AddressList
from twilio.rest.api.v2010.account.application import ApplicationList
from twilio.rest.api.v2010.account.authorized_connect_app import (
    AuthorizedConnectAppList,
)
from twilio.rest.api.v2010.account.available_phone_number_country import (
    AvailablePhoneNumberCountryList,
)
from twilio.rest.api.v2010.account.balance import BalanceList
from twilio.rest.api.v2010.account.call import CallList
from twilio.rest.api.v2010.account.conference import ConferenceList
from twilio.rest.api.v2010.account.connect_app import ConnectAppList
from twilio.rest.api.v2010.account.incoming_phone_number import IncomingPhoneNumberList
from twilio.rest.api.v2010.account.key import KeyList
from twilio.rest.api.v2010.account.message import MessageList
from twilio.rest.api.v2010.account.new_key import NewKeyList
from twilio.rest.api.v2010.account.new_signing_key import NewSigningKeyList
from twilio.rest.api.v2010.account.notification import NotificationList
from twilio.rest.api.v2010.account.outgoing_caller_id import OutgoingCallerIdList
from twilio.rest.api.v2010.account.queue import QueueList
from twilio.rest.api.v2010.account.recording import RecordingList
from twilio.rest.api.v2010.account.short_code import ShortCodeList
from twilio.rest.api.v2010.account.signing_key import SigningKeyList
from twilio.rest.api.v2010.account.sip import SipList
from twilio.rest.api.v2010.account.token import TokenList
from twilio.rest.api.v2010.account.transcription import TranscriptionList
from twilio.rest.api.v2010.account.usage import UsageList
from twilio.rest.api.v2010.account.validation_request import ValidationRequestList


class Api(ApiBase):
    @property
    def account(self) -> AccountContext:
        return self.v2010.account

    @property
    def accounts(self) -> AccountList:
        return self.v2010.accounts

    @property
    def addresses(self) -> AddressList:
        warn(
            "addresses is deprecated. Use account.addresses instead.",
            DeprecationWarning,
            stacklevel=2,
        )
        return self.account.addresses

    @property
    def applications(self) -> ApplicationList:
        warn(
            "applications is deprecated. Use account.applications instead.",
            DeprecationWarning,
            stacklevel=2,
        )
        return self.account.applications

    @property
    def authorized_connect_apps(self) -> AuthorizedConnectAppList:
        warn(
            "authorized_connect_apps is deprecated. Use account.authorized_connect_apps instead.",
            DeprecationWarning,
            stacklevel=2,
        )
        return self.account.authorized_connect_apps

    @property
    def available_phone_numbers(self) -> AvailablePhoneNumberCountryList:
        warn(
            "available_phone_numbers is deprecated. Use account.available_phone_numbers instead.",
            DeprecationWarning,
            stacklevel=2,
        )
        return self.account.available_phone_numbers

    @property
    def balance(self) -> BalanceList:
        warn(
            "balance is deprecated. Use account.balance instead.",
            DeprecationWarning,
            stacklevel=2,
        )
        return self.account.balance

    @property
    def calls(self) -> CallList:
        warn(
            "calls is deprecated. Use account.calls instead.",
            DeprecationWarning,
            stacklevel=2,
        )
        return self.account.calls

    @property
    def conferences(self) -> ConferenceList:
        warn(
            "conferences is deprecated. Use account.conferences instead.",
            DeprecationWarning,
            stacklevel=2,
        )
        return self.account.conferences

    @property
    def connect_apps(self) -> ConnectAppList:
        warn(
            "connect_apps is deprecated. Use account.connect_apps instead.",
            DeprecationWarning,
            stacklevel=2,
        )
        return self.account.connect_apps

    @property
    def incoming_phone_numbers(self) -> IncomingPhoneNumberList:
        warn(
            "incoming_phone_numbers is deprecated. Use account.incoming_phone_numbers instead.",
            DeprecationWarning,
            stacklevel=2,
        )
        return self.account.incoming_phone_numbers

    @property
    def keys(self) -> KeyList:
        warn(
            "keys is deprecated. Use account.keys instead.",
            DeprecationWarning,
            stacklevel=2,
        )
        return self.account.keys

    @property
    def messages(self) -> MessageList:
        warn(
            "messages is deprecated. Use account.messages instead.",
            DeprecationWarning,
            stacklevel=2,
        )
        return self.account.messages

    @property
    def new_keys(self) -> NewKeyList:
        warn(
            "new_keys is deprecated. Use account.new_keys instead.",
            DeprecationWarning,
            stacklevel=2,
        )
        return self.account.new_keys

    @property
    def new_signing_keys(self) -> NewSigningKeyList:
        warn(
            "new_signing_keys is deprecated. Use account.new_signing_keys instead.",
            DeprecationWarning,
            stacklevel=2,
        )
        return self.account.new_signing_keys

    @property
    def notifications(self) -> NotificationList:
        warn(
            "notifications is deprecated. Use account.notifications instead.",
            DeprecationWarning,
            stacklevel=2,
        )
        return self.account.notifications

    @property
    def outgoing_caller_ids(self) -> OutgoingCallerIdList:
        warn(
            "outgoing_caller_ids is deprecated. Use account.outgoing_caller_ids instead.",
            DeprecationWarning,
            stacklevel=2,
        )
        return self.account.outgoing_caller_ids

    @property
    def queues(self) -> QueueList:
        warn(
            "queues is deprecated. Use account.queues instead.",
            DeprecationWarning,
            stacklevel=2,
        )
        return self.account.queues

    @property
    def recordings(self) -> RecordingList:
        warn(
            "recordings is deprecated. Use account.recordings instead.",
            DeprecationWarning,
            stacklevel=2,
        )
        return self.account.recordings

    @property
    def signing_keys(self) -> SigningKeyList:
        warn(
            "signing_keys is deprecated. Use account.signing_keys instead.",
            DeprecationWarning,
            stacklevel=2,
        )
        return self.account.signing_keys

    @property
    def sip(self) -> SipList:
        warn(
            "sip is deprecated. Use account.sip instead.",
            DeprecationWarning,
            stacklevel=2,
        )
        return self.account.sip

    @property
    def short_codes(self) -> ShortCodeList:
        warn(
            "short_codes is deprecated. Use account.short_codes instead.",
            DeprecationWarning,
            stacklevel=2,
        )
        return self.account.short_codes

    @property
    def tokens(self) -> TokenList:
        warn(
            "tokens is deprecated. Use account.tokens instead.",
            DeprecationWarning,
            stacklevel=2,
        )
        return self.account.tokens

    @property
    def transcriptions(self) -> TranscriptionList:
        warn(
            "transcriptions is deprecated. Use account.transcriptions instead.",
            DeprecationWarning,
            stacklevel=2,
        )
        return self.account.transcriptions

    @property
    def usage(self) -> UsageList:
        warn(
            "usage is deprecated. Use account.usage instead.",
            DeprecationWarning,
            stacklevel=2,
        )
        return self.account.usage

    @property
    def validation_requests(self) -> ValidationRequestList:
        warn(
            "validation_requests is deprecated. Use account.validation_requests instead.",
            DeprecationWarning,
            stacklevel=2,
        )
        return self.account.validation_requests
