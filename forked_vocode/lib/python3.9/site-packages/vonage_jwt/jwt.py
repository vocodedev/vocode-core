import re
from time import time
from jwt import encode
from uuid import uuid4
from typing import Union


class JwtClient:
    """Object used to pass in an application ID and private key to the JWT generator."""

    def __init__(self, application_id: str, private_key: str):
        self._application_id = application_id

        try:
            self._set_private_key(private_key)
        except Exception as err:
            raise VonageJwtError(err)

        if self._application_id is None or self._private_key is None:
            raise VonageJwtError('Both of "application_id" and "private_key" are required.')

    def generate_application_jwt(self, jwt_options: dict = {}):
        """Generates a JWT for the specified Vonage application.
        If values for application_id and private_key are set on the JWTClient object,
        this method will use them. Otherwise, they can be specified directly.
        """

        iat = int(time())

        payload = jwt_options
        payload["application_id"] = self._application_id
        payload.setdefault("iat", iat)
        payload.setdefault("jti", str(uuid4()))
        payload.setdefault("exp", iat + (15 * 60))

        headers = {'alg': 'RS256', 'typ': 'JWT'}

        token = encode(payload, self._private_key, algorithm="RS256", headers=headers)
        return bytes(token, 'utf-8')

    def _set_private_key(self, key: Union[str, bytes]):
        if isinstance(key, (str, bytes)) and re.search("[.][a-zA-Z0-9_]+$", key):
            with open(key, "rb") as key_file:
                self._private_key = key_file.read()
        elif isinstance(key, str) and '-----BEGIN PRIVATE KEY-----' not in key:
            raise VonageJwtError(
                "If passing the private key directly as a string, it must be formatted correctly with newlines."
            )
        else:
            self._private_key = key


class VonageJwtError(Exception):
    """An error relating to the Vonage JWT Generator."""
