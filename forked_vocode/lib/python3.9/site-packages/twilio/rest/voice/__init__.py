from warnings import warn

from twilio.rest.voice.VoiceBase import VoiceBase
from twilio.rest.voice.v1.archived_call import ArchivedCallList
from twilio.rest.voice.v1.byoc_trunk import ByocTrunkList
from twilio.rest.voice.v1.connection_policy import ConnectionPolicyList
from twilio.rest.voice.v1.dialing_permissions import DialingPermissionsList
from twilio.rest.voice.v1.ip_record import IpRecordList
from twilio.rest.voice.v1.source_ip_mapping import SourceIpMappingList


class Voice(VoiceBase):
    @property
    def archived_calls(self) -> ArchivedCallList:
        warn(
            "archived_calls is deprecated. Use v1.archived_calls instead.",
            DeprecationWarning,
            stacklevel=2,
        )
        return self.v1.archived_calls

    @property
    def byoc_trunks(self) -> ByocTrunkList:
        warn(
            "byoc_trunks is deprecated. Use v1.byoc_trunks instead.",
            DeprecationWarning,
            stacklevel=2,
        )
        return self.v1.byoc_trunks

    @property
    def connection_policies(self) -> ConnectionPolicyList:
        warn(
            "connection_policies is deprecated. Use v1.connection_policies instead.",
            DeprecationWarning,
            stacklevel=2,
        )
        return self.v1.connection_policies

    @property
    def dialing_permissions(self) -> DialingPermissionsList:
        warn(
            "dialing_permissions is deprecated. Use v1.dialing_permissions instead.",
            DeprecationWarning,
            stacklevel=2,
        )
        return self.v1.dialing_permissions

    @property
    def ip_records(self) -> IpRecordList:
        warn(
            "ip_records is deprecated. Use v1.ip_records instead.",
            DeprecationWarning,
            stacklevel=2,
        )
        return self.v1.ip_records

    @property
    def source_ip_mappings(self) -> SourceIpMappingList:
        warn(
            "source_ip_mappings is deprecated. Use v1.source_ip_mappings instead.",
            DeprecationWarning,
            stacklevel=2,
        )
        return self.v1.source_ip_mappings
