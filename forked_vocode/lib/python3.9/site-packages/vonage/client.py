import vonage
from vonage_jwt.jwt import JwtClient

from .account import Account
from .application import ApplicationV2, Application
from .errors import *
from .meetings import Meetings
from .messages import Messages
from .number_insight import NumberInsight
from .number_management import Numbers
from .proactive_connect import ProactiveConnect
from .redact import Redact
from .short_codes import ShortCodes
from .sms import Sms
from .subaccounts import Subaccounts
from .users import Users
from .ussd import Ussd
from .voice import Voice
from .verify import Verify
from .verify2 import Verify2

import logging
from platform import python_version

import base64
import hashlib
import hmac
import os
import time

from requests import Response
from requests.adapters import HTTPAdapter
from requests.sessions import Session

string_types = (str, bytes)

try:
    from json import JSONDecodeError
except ImportError:
    JSONDecodeError = ValueError

logger = logging.getLogger("vonage")


class Client:
    """
    Create a Client object to start making calls to Vonage/Nexmo APIs.

    The credentials you provide when instantiating a Client determine which
    methods can be called. Consult the `Vonage API docs <https://developer.vonage.com/concepts/guides/authentication/>`
    for details of the authentication used by the APIs you wish to use, and instantiate your
    client with the appropriate credentials.

    :param str key: Your Vonage API key
    :param str secret: Your Vonage API secret.
    :param str signature_secret: Your Vonage API signature secret.
        You may need to have this enabled by Vonage support. It is only used for SMS authentication.
    :param str signature_method:
        The encryption method used for signature encryption. This must match the method
        configured in the Vonage Dashboard. We recommend `sha256` or `sha512`.
        This should be one of `md5`, `sha1`, `sha256`, or `sha512` if using HMAC digests.
        If you want to use a simple MD5 hash, leave this as `None`.
    :param str application_id: Your application ID if calling methods which use JWT authentication.
    :param str private_key: Your private key, for calling methods which use JWT authentication.
        This should either be a str containing the key in its PEM form, or a path to a private key file.
    :param str app_name: This optional value is added to the user-agent header
        provided by this library and can be used to track your app statistics.
    :param str app_version: This optional value is added to the user-agent header
        provided by this library and can be used to track your app statistics.
    :param timeout: (optional) How many seconds to wait for the server to send data
        before giving up, as a float, or a (connect timeout, read
        timeout) tuple. If set this timeout is used for every call to the Vonage enpoints
    :type timeout: float or tuple
    """

    def __init__(
        self,
        key=None,
        secret=None,
        signature_secret=None,
        signature_method=None,
        application_id=None,
        private_key=None,
        app_name=None,
        app_version=None,
        timeout=None,
        pool_connections=10,
        pool_maxsize=10,
        max_retries=3,
    ):
        self.api_key = key or os.environ.get("VONAGE_API_KEY", None)
        self.api_secret = secret or os.environ.get("VONAGE_API_SECRET", None)

        self.signature_secret = signature_secret or os.environ.get("VONAGE_SIGNATURE_SECRET", None)
        self.signature_method = signature_method or os.environ.get("VONAGE_SIGNATURE_METHOD", None)

        if self.signature_method in {
            "md5",
            "sha1",
            "sha256",
            "sha512",
        }:
            self.signature_method = getattr(hashlib, signature_method)

        if private_key is not None and application_id is not None:
            self._jwt_client = JwtClient(application_id, private_key)

        self._jwt_claims = {}
        self._host = "rest.nexmo.com"
        self._api_host = "api.nexmo.com"
        self._meetings_api_host = "api-eu.vonage.com/v1/meetings"
        self._proactive_connect_host = "api-eu.vonage.com"

        user_agent = f"vonage-python/{vonage.__version__} python/{python_version()}"

        if app_name and app_version:
            user_agent += f" {app_name}/{app_version}"

        self.headers = {
            "User-Agent": user_agent,
            "Accept": "application/json",
        }

        self.account = Account(self)
        self.application = Application(self)
        self.meetings = Meetings(self)
        self.messages = Messages(self)
        self.number_insight = NumberInsight(self)
        self.numbers = Numbers(self)
        self.proactive_connect = ProactiveConnect(self)
        self.short_codes = ShortCodes(self)
        self.sms = Sms(self)
        self.subaccounts = Subaccounts(self)
        self.users = Users(self)
        self.ussd = Ussd(self)
        self.verify = Verify(self)
        self.verify2 = Verify2(self)
        self.voice = Voice(self)

        self.timeout = timeout
        self.session = Session()
        self.adapter = HTTPAdapter(
            pool_connections=pool_connections,
            pool_maxsize=pool_maxsize,
            max_retries=max_retries,
        )
        self.session.mount("https://", self.adapter)

    # Gets and sets _host attribute
    def host(self, value=None):
        if value is None:
            return self._host
        else:
            self._host = value

    # Gets and sets _api_host attribute
    def api_host(self, value=None):
        if value is None:
            return self._api_host
        else:
            self._api_host = value

    # Gets and sets _meetings_api_host attribute
    def meetings_api_host(self, value=None):
        if value is None:
            return self._meetings_api_host
        else:
            self._meetings_api_host = value

    def proactive_connect_host(self, value=None):
        if value is None:
            return self._proactive_connect_host
        else:
            self._proactive_connect_host = value

    def auth(self, params=None, **kwargs):
        self._jwt_claims = params or kwargs

    def check_signature(self, params):
        params = dict(params)
        signature = params.pop("sig", "").lower()
        return hmac.compare_digest(signature, self.signature(params))

    def signature(self, params):
        if self.signature_method:
            hasher = hmac.new(
                self.signature_secret.encode(),
                digestmod=self.signature_method,
            )
        else:
            hasher = hashlib.md5()

        # Add timestamp if not already present
        if not params.get("timestamp"):
            params["timestamp"] = int(time.time())

        for key in sorted(params):
            value = params[key]

            if isinstance(value, str):
                value = value.replace("&", "_").replace("=", "_")

            hasher.update(f"&{key}={value}".encode("utf-8"))

        if self.signature_method is None:
            hasher.update(self.signature_secret.encode())

        return hasher.hexdigest()

    def get(self, host, request_uri, params=None, auth_type=None):
        uri = f"https://{host}{request_uri}"
        self._request_headers = self.headers

        if auth_type == 'jwt':
            self._request_headers['Authorization'] = self._create_jwt_auth_string()
        elif auth_type == 'params':
            params = dict(
                params or {},
                api_key=self.api_key,
                api_secret=self.api_secret,
            )
        elif auth_type == 'header':
            self._request_headers['Authorization'] = self._create_header_auth_string()
        else:
            raise InvalidAuthenticationTypeError(
                f'Invalid authentication type. Must be one of "jwt", "header" or "params".'
            )

        logger.debug(
            f"GET to {repr(uri)} with params {repr(params)}, headers {repr(self._request_headers)}"
        )
        return self.parse(
            host,
            self.session.get(
                uri,
                params=params,
                headers=self._request_headers,
                timeout=self.timeout,
            ),
        )

    def post(
        self,
        host,
        request_uri,
        params,
        auth_type=None,
        body_is_json=True,
        supports_signature_auth=False,
    ):
        """
        Low-level method to make a post request to an API server.
        This method automatically adds authentication, picking the first applicable authentication method from the following:
        - If the supports_signature_auth param is True, and the client was instantiated with a signature_secret,
            then signature authentication will be used.
        :param bool supports_signature_auth: Preferentially use signature authentication if a signature_secret was provided
            when initializing this client.
        """
        uri = f"https://{host}{request_uri}"
        self._request_headers = self.headers

        if supports_signature_auth and self.signature_secret:
            params["api_key"] = self.api_key
            params["sig"] = self.signature(params)
        elif auth_type == 'jwt':
            self._request_headers['Authorization'] = self._create_jwt_auth_string()
        elif auth_type == 'params':
            params = dict(
                params,
                api_key=self.api_key,
                api_secret=self.api_secret,
            )
        elif auth_type == 'header':
            self._request_headers['Authorization'] = self._create_header_auth_string()
        else:
            raise InvalidAuthenticationTypeError(
                f'Invalid authentication type. Must be one of "jwt", "header" or "params".'
            )

        logger.debug(
            f"POST to {repr(uri)} with params {repr(params)}, headers {repr(self._request_headers)}"
        )
        if body_is_json:
            return self.parse(
                host,
                self.session.post(
                    uri,
                    json=params,
                    headers=self._request_headers,
                    timeout=self.timeout,
                ),
            )
        else:
            return self.parse(
                host,
                self.session.post(
                    uri,
                    data=params,
                    headers=self._request_headers,
                    timeout=self.timeout,
                ),
            )

    def put(self, host, request_uri, params, auth_type=None):
        uri = f"https://{host}{request_uri}"
        self._request_headers = self.headers

        if auth_type == 'jwt':
            self._request_headers['Authorization'] = self._create_jwt_auth_string()
        elif auth_type == 'header':
            self._request_headers['Authorization'] = self._create_header_auth_string()
        else:
            raise InvalidAuthenticationTypeError(
                f'Invalid authentication type. Must be one of "jwt", "header" or "params".'
            )

        logger.debug(
            f"PUT to {repr(uri)} with params {repr(params)}, headers {repr(self._request_headers)}"
        )
        # All APIs that currently use put methods require a json-formatted body so don't need to check this
        return self.parse(
            host,
            self.session.put(
                uri,
                json=params,
                headers=self._request_headers,
                timeout=self.timeout,
            ),
        )

    def patch(self, host, request_uri, params, auth_type=None):
        uri = f"https://{host}{request_uri}"
        self._request_headers = self.headers

        if auth_type == 'jwt':
            self._request_headers['Authorization'] = self._create_jwt_auth_string()
        elif auth_type == 'header':
            self._request_headers['Authorization'] = self._create_header_auth_string()
        else:
            raise InvalidAuthenticationTypeError(f"""Invalid authentication type.""")

        logger.debug(
            f"PATCH to {repr(uri)} with params {repr(params)}, headers {repr(self._request_headers)}"
        )
        # Only newer APIs (that expect json-bodies) currently use this method, so we will always send a json-formatted body
        return self.parse(
            host,
            self.session.patch(
                uri,
                json=params,
                headers=self._request_headers,
            ),
        )

    def delete(self, host, request_uri, params=None, auth_type=None):
        uri = f"https://{host}{request_uri}"
        self._request_headers = self.headers

        if auth_type == 'jwt':
            self._request_headers['Authorization'] = self._create_jwt_auth_string()
        elif auth_type == 'header':
            self._request_headers['Authorization'] = self._create_header_auth_string()
        else:
            raise InvalidAuthenticationTypeError(
                f'Invalid authentication type. Must be one of "jwt", "header" or "params".'
            )

        logger.debug(f"DELETE to {repr(uri)} with headers {repr(self._request_headers)}")
        if params is not None:
            logger.debug(f"DELETE call has params {repr(params)}")
        return self.parse(
            host,
            self.session.delete(
                uri,
                headers=self._request_headers,
                timeout=self.timeout,
                params=params,
            ),
        )

    def parse(self, host, response: Response):
        logger.debug(f"Response headers {repr(response.headers)}")
        if response.status_code == 401:
            raise AuthenticationError("Authentication failed.")
        elif response.status_code == 204:
            return None
        elif 200 <= response.status_code < 300:
            # Strip off any encoding from the content-type header:
            try:
                content_mime = response.headers.get("content-type").split(";", 1)[0]
            except AttributeError:
                if response.json() is None:
                    return None
            if content_mime == "application/json":
                try:
                    return response.json()
                except JSONDecodeError:
                    pass
            else:
                return response.content
        elif 400 <= response.status_code < 500:
            logger.warning(f"Client error: {response.status_code} {repr(response.content)}")
            message = f"{response.status_code} response from {host}"

            # Test for standard error format:
            try:
                error_data = response.json()
                if "type" in error_data and "title" in error_data and "detail" in error_data:
                    title = error_data["title"]
                    detail = error_data["detail"]
                    type = error_data["type"]
                    message = f"{title}: {detail} ({type}){self._add_individual_errors(error_data)}"
                elif 'status' in error_data and 'message' in error_data and 'name' in error_data:
                    message = (
                        f'Status Code {error_data["status"]}: {error_data["name"]}: {error_data["message"]}'
                        f'{self._add_individual_errors(error_data)}'
                    )
                else:
                    message = error_data
            except JSONDecodeError:
                pass
            raise ClientError(message)

        elif 500 <= response.status_code < 600:
            logger.warning(f"Server error: {response.status_code} {repr(response.content)}")
            message = f"{response.status_code} response from {host}"
            raise ServerError(message)

    def _add_individual_errors(self, error_data):
        message = ''
        if 'errors' in error_data:
            for error in error_data["errors"]:
                message += f"\nError: {error}"
        return message

    def _create_jwt_auth_string(self):
        return b"Bearer " + self._generate_application_jwt()

    def _generate_application_jwt(self):
        try:
            return self._jwt_client.generate_application_jwt(self._jwt_claims)
        except AttributeError as err:
            if '_jwt_client' in str(err):
                raise ClientError(
                    'JWT generation failed. Check that you passed in valid values for "application_id" and "private_key".'
                )
            else:
                raise err

    def _create_header_auth_string(self):
        hash = base64.b64encode(f"{self.api_key}:{self.api_secret}".encode("utf-8")).decode("ascii")
        return f"Basic {hash}"
