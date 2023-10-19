from .errors import RedactError

from deprecated import deprecated


@deprecated(
    version='3.0.0',
    reason='This is a dev preview product and as such is not supported in this SDK.',
)
class Redact:
    auth_type = 'header'

    allowed_product_names = {'sms', 'voice', 'number-insight', 'verify', 'verify-sdk', 'messages'}

    def __init__(self, client):
        self._client = client

    def redact_transaction(self, id: str, product: str, type=None):
        self._check_allowed_product_name(product)
        params = {"id": id, "product": product}
        if type is not None:
            params["type"] = type
        return self._client.post(
            self._client.api_host(), "/v1/redact/transaction", params, auth_type=Redact.auth_type
        )

    def _check_allowed_product_name(self, product):
        if product not in self.allowed_product_names:
            raise RedactError(
                f'Invalid product name in redact request. Must be one of {self.allowed_product_names}.'
            )
