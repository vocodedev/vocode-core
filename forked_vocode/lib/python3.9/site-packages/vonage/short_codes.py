class ShortCodes:
    auth_type = 'params'
    defaults = {'auth_type': auth_type, 'body_is_json': False}

    def __init__(self, client):
        self._client = client

    def send_2fa_message(self, params=None, **kwargs):
        return self._client.post(
            self._client.host(), "/sc/us/2fa/json", params or kwargs, **ShortCodes.defaults
        )

    def send_event_alert_message(self, params=None, **kwargs):
        return self._client.post(
            self._client.host(), "/sc/us/alert/json", params or kwargs, **ShortCodes.defaults
        )

    def send_marketing_message(self, params=None, **kwargs):
        return self._client.post(
            self._client.host(), "/sc/us/marketing/json", params or kwargs, **ShortCodes.defaults
        )

    def get_event_alert_numbers(self):
        return self._client.get(
            self._client.host(), "/sc/us/alert/opt-in/query/json", auth_type=ShortCodes.auth_type
        )

    def resubscribe_event_alert_number(self, params=None, **kwargs):
        return self._client.post(
            self._client.host(),
            "/sc/us/alert/opt-in/manage/json",
            params or kwargs,
            **ShortCodes.defaults,
        )
