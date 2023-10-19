from twilio.jwt.taskrouter import TaskRouterCapabilityToken


class WorkerCapabilityToken(TaskRouterCapabilityToken):
    def __init__(
        self, account_sid, auth_token, workspace_sid, worker_sid, ttl=3600, **kwargs
    ):
        """
        :param kwargs:
            All kwarg parameters supported by TaskRouterCapabilityToken
            :param bool allow_fetch_activities: shortcut to calling allow_fetch_activities,
                                                defaults to True
            :param bool allow_fetch_reservations: shortcut to calling allow_fetch_reservations,
                                                  defaults to True
            :param bool allow_fetch_worker_reservations: shortcut to calling allow_fetch_worker_reservations,
                                                         defaults to True
            :param bool allow_update_activities: shortcut to calling allow_update_activities,
                                                 defaults to False
            :param bool allow_update_reservations: shortcut to calling allow_update_reservations,
                                                   defaults to False
        """
        super(WorkerCapabilityToken, self).__init__(
            account_sid=account_sid,
            auth_token=auth_token,
            workspace_sid=workspace_sid,
            channel_id=worker_sid,
            ttl=ttl,
            **kwargs
        )

        if kwargs.get("allow_fetch_activities", True):
            self.allow_fetch_activities()
        if kwargs.get("allow_fetch_reservations", True):
            self.allow_fetch_reservations()
        if kwargs.get("allow_fetch_worker_reservations", True):
            self.allow_fetch_worker_reservations()
        if kwargs.get("allow_update_activities", False):
            self.allow_update_activities()
        if kwargs.get("allow_update_reservations", False):
            self.allow_update_reservations()

    @property
    def resource_url(self):
        return "{}/Workers/{}".format(self.workspace_url, self.channel_id)

    @property
    def channel_prefix(self):
        return "WK"

    def allow_fetch_activities(self):
        self._make_policy(self.workspace_url + "/Activities", "GET", True)

    def allow_fetch_reservations(self):
        self._make_policy(self.workspace_url + "/Tasks/**", "GET", True)

    def allow_fetch_worker_reservations(self):
        self._make_policy(self.resource_url + "/Reservations/**", "GET", True)

    def allow_update_activities(self):
        post_filter = {"ActivitySid": {"required": True}}
        self._make_policy(self.resource_url, "POST", True, post_filter=post_filter)

    def allow_update_reservations(self):
        self._make_policy(self.workspace_url + "/Tasks/**", "POST", True)
        self._make_policy(self.resource_url + "/Reservations/**", "POST", True)

    def __str__(self):
        return "<WorkerCapabilityToken {}>".format(self.to_jwt())


class TaskQueueCapabilityToken(TaskRouterCapabilityToken):
    def __init__(
        self, account_sid, auth_token, workspace_sid, task_queue_sid, ttl=3600, **kwargs
    ):
        super(TaskQueueCapabilityToken, self).__init__(
            account_sid=account_sid,
            auth_token=auth_token,
            workspace_sid=workspace_sid,
            channel_id=task_queue_sid,
            ttl=ttl,
            **kwargs
        )

    @property
    def resource_url(self):
        return "{}/TaskQueues/{}".format(self.workspace_url, self.channel_id)

    @property
    def channel_prefix(self):
        return "WQ"

    def __str__(self):
        return "<TaskQueueCapabilityToken {}>".format(self.to_jwt())


class WorkspaceCapabilityToken(TaskRouterCapabilityToken):
    def __init__(self, account_sid, auth_token, workspace_sid, ttl=3600, **kwargs):
        super(WorkspaceCapabilityToken, self).__init__(
            account_sid=account_sid,
            auth_token=auth_token,
            workspace_sid=workspace_sid,
            channel_id=workspace_sid,
            ttl=ttl,
            **kwargs
        )

    @property
    def resource_url(self):
        return self.workspace_url

    @property
    def channel_prefix(self):
        return "WS"

    def __str__(self):
        return "<WorkspaceCapabilityToken {}>".format(self.to_jwt())
