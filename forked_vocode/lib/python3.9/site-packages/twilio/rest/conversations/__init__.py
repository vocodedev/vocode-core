from warnings import warn

from twilio.rest.conversations.ConversationsBase import ConversationsBase
from twilio.rest.conversations.v1.address_configuration import AddressConfigurationList
from twilio.rest.conversations.v1.configuration import ConfigurationList
from twilio.rest.conversations.v1.conversation import ConversationList
from twilio.rest.conversations.v1.credential import CredentialList
from twilio.rest.conversations.v1.participant_conversation import (
    ParticipantConversationList,
)
from twilio.rest.conversations.v1.role import RoleList
from twilio.rest.conversations.v1.service import ServiceList
from twilio.rest.conversations.v1.user import UserList


class Conversations(ConversationsBase):
    @property
    def configuration(self) -> ConfigurationList:
        warn(
            "configuration is deprecated. Use v1.configuration instead.",
            DeprecationWarning,
            stacklevel=2,
        )
        return self.v1.configuration

    @property
    def address_configurations(self) -> AddressConfigurationList:
        warn(
            "address_configurations is deprecated. Use v1.address_configurations instead.",
            DeprecationWarning,
            stacklevel=2,
        )
        return self.v1.address_configurations

    @property
    def conversations(self) -> ConversationList:
        warn(
            "conversations is deprecated. Use v1.conversations instead.",
            DeprecationWarning,
            stacklevel=2,
        )
        return self.v1.conversations

    @property
    def credentials(self) -> CredentialList:
        warn(
            "credentials is deprecated. Use v1.credentials instead.",
            DeprecationWarning,
            stacklevel=2,
        )
        return self.v1.credentials

    @property
    def participant_conversations(self) -> ParticipantConversationList:
        warn(
            "participant_conversations is deprecated. Use v1.participant_conversations instead.",
            DeprecationWarning,
            stacklevel=2,
        )
        return self.v1.participant_conversations

    @property
    def roles(self) -> RoleList:
        warn(
            "roles is deprecated. Use v1.roles instead.",
            DeprecationWarning,
            stacklevel=2,
        )
        return self.v1.roles

    @property
    def services(self) -> ServiceList:
        warn(
            "services is deprecated. Use v1.services instead.",
            DeprecationWarning,
            stacklevel=2,
        )
        return self.v1.services

    @property
    def users(self) -> UserList:
        warn(
            "users is deprecated. Use v1.users instead.",
            DeprecationWarning,
            stacklevel=2,
        )
        return self.v1.users
