from .errors import CallbackRequiredError


class NumberInsight:
    auth_type = 'params'

    def __init__(self, client):
        self._client = client

    def get_basic_number_insight(self, params=None, **kwargs):
        return self._client.get(
            self._client.api_host(),
            "/ni/basic/json",
            params or kwargs,
            auth_type=NumberInsight.auth_type,
        )

    def get_standard_number_insight(self, params=None, **kwargs):
        return self._client.get(
            self._client.api_host(),
            "/ni/standard/json",
            params or kwargs,
            auth_type=NumberInsight.auth_type,
        )

    def get_advanced_number_insight(self, params=None, **kwargs):
        return self._client.get(
            self._client.api_host(),
            "/ni/advanced/json",
            params or kwargs,
            auth_type=NumberInsight.auth_type,
        )

    def get_async_advanced_number_insight(self, params=None, **kwargs):
        argoparams = params or kwargs
        if (
            "callback" in argoparams
            and type(argoparams["callback"]) == str
            and argoparams["callback"] != ""
        ):
            return self._client.get(
                self._client.api_host(),
                "/ni/advanced/async/json",
                params or kwargs,
                auth_type=NumberInsight.auth_type,
            )
        else:
            raise CallbackRequiredError("A callback is needed for async advanced number insight")
