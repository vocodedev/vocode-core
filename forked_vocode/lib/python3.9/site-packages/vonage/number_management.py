class Numbers:
    auth_type = 'header'
    defaults = {'auth_type': auth_type, 'body_is_json': False}

    def __init__(self, client):
        self._client = client

    def get_account_numbers(self, params=None, **kwargs):
        return self._client.get(
            self._client.host(), "/account/numbers", params or kwargs, auth_type=Numbers.auth_type
        )

    def get_available_numbers(self, country_code, params=None, **kwargs):
        return self._client.get(
            self._client.host(),
            "/number/search",
            dict(params or kwargs, country=country_code),
            auth_type=Numbers.auth_type,
        )

    def buy_number(self, params=None, **kwargs):
        return self._client.post(
            self._client.host(), "/number/buy", params or kwargs, **Numbers.defaults
        )

    def cancel_number(self, params=None, **kwargs):
        return self._client.post(
            self._client.host(), "/number/cancel", params or kwargs, **Numbers.defaults
        )

    def update_number(self, params=None, **kwargs):
        return self._client.post(
            self._client.host(), "/number/update", params or kwargs, **Numbers.defaults
        )
