from twilio.jwt import Jwt


class TaskRouterCapabilityToken(Jwt):
    VERSION = "v1"
    DOMAIN = "https://taskrouter.twilio.com"
    EVENTS_BASE_URL = "https://event-bridge.twilio.com/v1/wschannels"
    ALGORITHM = "HS256"

    def __init__(self, account_sid, auth_token, workspace_sid, channel_id, **kwargs):
        """
        :param str account_sid: Twilio account sid
        :param str auth_token: Twilio auth token used to sign the JWT
        :param str workspace_sid: TaskRouter workspace sid
        :param str channel_id: TaskRouter channel sid
        :param kwargs:
            :param bool allow_web_sockets: shortcut to calling allow_web_sockets, defaults to True
            :param bool allow_fetch_self: shortcut to calling allow_fetch_self, defaults to True
            :param bool allow_update_self: shortcut to calling allow_update_self, defaults to False
            :param bool allow_delete_self: shortcut to calling allow_delete_self, defaults to False
            :param bool allow_fetch_subresources: shortcut to calling allow_fetch_subresources,
                                                  defaults to False
            :param bool allow_update_subresources: shortcut to calling allow_update_subresources,
                                                   defaults to False
            :param bool allow_delete_subresources: shortcut to calling allow_delete_subresources,
                                                   defaults to False
        :returns a new TaskRouterCapabilityToken with capabilities set depending on kwargs.
        """
        super(TaskRouterCapabilityToken, self).__init__(
            secret_key=auth_token,
            issuer=account_sid,
            algorithm=self.ALGORITHM,
            nbf=kwargs.get("nbf", Jwt.GENERATE),
            ttl=kwargs.get("ttl", 3600),
            valid_until=kwargs.get("valid_until", None),
        )

        self._validate_inputs(account_sid, workspace_sid, channel_id)

        self.account_sid = account_sid
        self.auth_token = auth_token
        self.workspace_sid = workspace_sid
        self.channel_id = channel_id
        self.policies = []

        if kwargs.get("allow_web_sockets", True):
            self.allow_web_sockets()
        if kwargs.get("allow_fetch_self", True):
            self.allow_fetch_self()
        if kwargs.get("allow_update_self", False):
            self.allow_update_self()
        if kwargs.get("allow_delete_self", False):
            self.allow_delete_self()
        if kwargs.get("allow_fetch_subresources", False):
            self.allow_fetch_subresources()
        if kwargs.get("allow_delete_subresources", False):
            self.allow_delete_subresources()
        if kwargs.get("allow_update_subresources", False):
            self.allow_update_subresources()

    @property
    def workspace_url(self):
        return "{}/{}/Workspaces/{}".format(
            self.DOMAIN, self.VERSION, self.workspace_sid
        )

    @property
    def resource_url(self):
        raise NotImplementedError("Subclass must set its specific resource_url.")

    @property
    def channel_prefix(self):
        raise NotImplementedError(
            "Subclass must set its specific channel_id sid prefix."
        )

    def allow_fetch_self(self):
        self._make_policy(self.resource_url, "GET", True)

    def allow_update_self(self):
        self._make_policy(self.resource_url, "POST", True)

    def allow_delete_self(self):
        self._make_policy(self.resource_url, "DELETE", True)

    def allow_fetch_subresources(self):
        self._make_policy(self.resource_url + "/**", "GET", True)

    def allow_update_subresources(self):
        self._make_policy(self.resource_url + "/**", "POST", True)

    def allow_delete_subresources(self):
        self._make_policy(self.resource_url + "/**", "DELETE", True)

    def allow_web_sockets(self, channel_id=None):
        channel_id = channel_id or self.channel_id
        web_socket_url = "{}/{}/{}".format(
            self.EVENTS_BASE_URL, self.account_sid, channel_id
        )
        self._make_policy(web_socket_url, "GET", True)
        self._make_policy(web_socket_url, "POST", True)

    def _generate_payload(self):
        payload = {
            "account_sid": self.account_sid,
            "workspace_sid": self.workspace_sid,
            "channel": self.channel_id,
            "version": self.VERSION,
            "friendly_name": self.channel_id,
            "policies": self.policies,
        }

        if self.channel_id.startswith("WK"):
            payload["worker_sid"] = self.channel_id
        elif self.channel_id.startswith("WQ"):
            payload["taskqueue_sid"] = self.channel_id

        return payload

    def _make_policy(self, url, method, allowed, query_filter=None, post_filter=None):
        self.policies.append(
            {
                "url": url,
                "method": method.upper(),
                "allow": allowed,
                "query_filter": query_filter or {},
                "post_filter": post_filter or {},
            }
        )

    def _validate_inputs(self, account_sid, workspace_sid, channel_id):
        if not account_sid or not account_sid.startswith("AC"):
            raise ValueError("Invalid account sid provided {}".format(account_sid))

        if not workspace_sid or not workspace_sid.startswith("WS"):
            raise ValueError("Invalid workspace sid provided {}".format(workspace_sid))

        if not channel_id or not channel_id.startswith(self.channel_prefix):
            raise ValueError("Invalid channel id provided {}".format(channel_id))

    def __str__(self):
        return "<TaskRouterCapabilityToken {}>".format(self.to_jwt())
