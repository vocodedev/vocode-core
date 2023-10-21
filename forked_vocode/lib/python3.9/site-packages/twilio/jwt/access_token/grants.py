from twilio.jwt.access_token import AccessTokenGrant
import warnings
import functools


def deprecated(func):
    """This is a decorator which can be used to mark functions
    as deprecated. It will result in a warning being emitted
    when the function is used."""

    @functools.wraps(func)
    def new_func(*args, **kwargs):
        warnings.simplefilter("always", DeprecationWarning)
        warnings.warn(
            "Call to deprecated function {}.".format(func.__name__),
            category=DeprecationWarning,
            stacklevel=2,
        )
        warnings.simplefilter("default", DeprecationWarning)
        return func(*args, **kwargs)

    return new_func


class ChatGrant(AccessTokenGrant):
    """Grant to access Twilio Chat"""

    def __init__(
        self,
        service_sid=None,
        endpoint_id=None,
        deployment_role_sid=None,
        push_credential_sid=None,
    ):
        self.service_sid = service_sid
        self.endpoint_id = endpoint_id
        self.deployment_role_sid = deployment_role_sid
        self.push_credential_sid = push_credential_sid

    @property
    def key(self):
        return "chat"

    def to_payload(self):
        grant = {}
        if self.service_sid:
            grant["service_sid"] = self.service_sid
        if self.endpoint_id:
            grant["endpoint_id"] = self.endpoint_id
        if self.deployment_role_sid:
            grant["deployment_role_sid"] = self.deployment_role_sid
        if self.push_credential_sid:
            grant["push_credential_sid"] = self.push_credential_sid

        return grant


class SyncGrant(AccessTokenGrant):
    """Grant to access Twilio Sync"""

    def __init__(self, service_sid=None, endpoint_id=None):
        self.service_sid = service_sid
        self.endpoint_id = endpoint_id

    @property
    def key(self):
        return "data_sync"

    def to_payload(self):
        grant = {}
        if self.service_sid:
            grant["service_sid"] = self.service_sid
        if self.endpoint_id:
            grant["endpoint_id"] = self.endpoint_id

        return grant


class VoiceGrant(AccessTokenGrant):
    """Grant to access Twilio Programmable Voice"""

    def __init__(
        self,
        incoming_allow=None,
        outgoing_application_sid=None,
        outgoing_application_params=None,
        push_credential_sid=None,
        endpoint_id=None,
    ):
        self.incoming_allow = incoming_allow
        """ :type : bool """
        self.outgoing_application_sid = outgoing_application_sid
        """ :type : str """
        self.outgoing_application_params = outgoing_application_params
        """ :type : dict """
        self.push_credential_sid = push_credential_sid
        """ :type : str """
        self.endpoint_id = endpoint_id
        """ :type : str """

    @property
    def key(self):
        return "voice"

    def to_payload(self):
        grant = {}
        if self.incoming_allow is True:
            grant["incoming"] = {}
            grant["incoming"]["allow"] = True

        if self.outgoing_application_sid:
            grant["outgoing"] = {}
            grant["outgoing"]["application_sid"] = self.outgoing_application_sid

            if self.outgoing_application_params:
                grant["outgoing"]["params"] = self.outgoing_application_params

        if self.push_credential_sid:
            grant["push_credential_sid"] = self.push_credential_sid

        if self.endpoint_id:
            grant["endpoint_id"] = self.endpoint_id

        return grant


class VideoGrant(AccessTokenGrant):
    """Grant to access Twilio Video"""

    def __init__(self, room=None):
        self.room = room

    @property
    def key(self):
        return "video"

    def to_payload(self):
        grant = {}
        if self.room:
            grant["room"] = self.room

        return grant


class TaskRouterGrant(AccessTokenGrant):
    """Grant to access Twilio TaskRouter"""

    def __init__(self, workspace_sid=None, worker_sid=None, role=None):
        self.workspace_sid = workspace_sid
        self.worker_sid = worker_sid
        self.role = role

    @property
    def key(self):
        return "task_router"

    def to_payload(self):
        grant = {}
        if self.workspace_sid:
            grant["workspace_sid"] = self.workspace_sid
        if self.worker_sid:
            grant["worker_sid"] = self.worker_sid
        if self.role:
            grant["role"] = self.role

        return grant


class PlaybackGrant(AccessTokenGrant):
    """Grant to access Twilio Live stream"""

    def __init__(self, grant=None):
        """Initialize a PlaybackGrant with a grant retrieved from the Twilio API."""
        self.grant = grant

    @property
    def key(self):
        """Return the grant's key."""
        return "player"

    def to_payload(self):
        """Return the grant."""
        return self.grant
