from .errors import PricingTypeError

from deprecated import deprecated


class Account:
    account_auth_type = 'params'
    pricing_auth_type = 'params'
    secrets_auth_type = 'header'

    allowed_pricing_types = {'sms', 'sms-transit', 'voice'}

    def __init__(self, client):
        self._client = client

    def get_balance(self):
        return self._client.get(
            self._client.host(), "/account/get-balance", auth_type=Account.account_auth_type
        )

    def topup(self, params=None, **kwargs):
        return self._client.post(
            self._client.host(),
            "/account/top-up",
            params or kwargs,
            auth_type=Account.account_auth_type,
            body_is_json=False,
        )

    def get_country_pricing(self, country_code: str, type: str = 'sms'):
        self._check_allowed_pricing_type(type)
        return self._client.get(
            self._client.host(),
            f"/account/get-pricing/outbound/{type}",
            {"country": country_code},
            auth_type=Account.pricing_auth_type,
        )

    def get_all_countries_pricing(self, type: str = 'sms'):
        self._check_allowed_pricing_type(type)
        return self._client.get(
            self._client.host(),
            f"/account/get-full-pricing/outbound/{type}",
            auth_type=Account.pricing_auth_type,
        )

    def get_prefix_pricing(self, prefix: str, type: str = 'sms'):
        self._check_allowed_pricing_type(type)
        return self._client.get(
            self._client.host(),
            f"/account/get-prefix-pricing/outbound/{type}",
            {"prefix": prefix},
            auth_type=Account.pricing_auth_type,
        )

    @deprecated(version='3.0.0', reason='The "account/get-phone-pricing" endpoint is deprecated.')
    def get_sms_pricing(self, number: str):
        return self._client.get(
            self._client.host(),
            "/account/get-phone-pricing/outbound/sms",
            {"phone": number},
            auth_type=Account.pricing_auth_type,
        )

    @deprecated(version='3.0.0', reason='The "account/get-phone-pricing" endpoint is deprecated.')
    def get_voice_pricing(self, number: str):
        return self._client.get(
            self._client.host(),
            "/account/get-phone-pricing/outbound/voice",
            {"phone": number},
            auth_type=Account.pricing_auth_type,
        )

    def update_default_sms_webhook(self, params=None, **kwargs):
        return self._client.post(
            self._client.host(),
            "/account/settings",
            params or kwargs,
            auth_type=Account.account_auth_type,
            body_is_json=False,
        )

    def list_secrets(self, api_key):
        return self._client.get(
            self._client.api_host(),
            f"/accounts/{api_key}/secrets",
            auth_type=Account.secrets_auth_type,
        )

    def get_secret(self, api_key, secret_id):
        return self._client.get(
            self._client.api_host(),
            f"/accounts/{api_key}/secrets/{secret_id}",
            auth_type=Account.secrets_auth_type,
        )

    def create_secret(self, api_key, secret):
        body = {"secret": secret}
        return self._client.post(
            self._client.api_host(),
            f"/accounts/{api_key}/secrets",
            body,
            auth_type=Account.secrets_auth_type,
            body_is_json=False,
        )

    def revoke_secret(self, api_key, secret_id):
        return self._client.delete(
            self._client.api_host(),
            f"/accounts/{api_key}/secrets/{secret_id}",
            auth_type=Account.secrets_auth_type,
        )

    def _check_allowed_pricing_type(self, type):
        if type not in Account.allowed_pricing_types:
            raise PricingTypeError('Invalid pricing type specified.')
