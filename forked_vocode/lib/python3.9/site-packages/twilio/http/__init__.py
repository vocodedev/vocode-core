from logging import Logger
from typing import Any, Dict, Optional, Tuple
from urllib.parse import urlencode

from requests import Response

from twilio.base.exceptions import TwilioException
from twilio.http.request import Request as TwilioRequest
from twilio.http.response import Response as TwilioResponse


class HttpClient(object):
    def __init__(self, logger: Logger, is_async: bool, timeout: Optional[float] = None):
        """
        Constructor for the abstract HTTP client

        :param logger
        :param is_async: Whether the client supports async request calls.
        :param timeout: Timeout for the requests.
                        Timeout should never be zero (0) or less.
        """
        self.logger = logger
        self.is_async = is_async

        if timeout is not None and timeout <= 0:
            raise ValueError(timeout)
        self.timeout = timeout

        self._test_only_last_request: Optional[TwilioRequest] = None
        self._test_only_last_response: Optional[TwilioResponse] = None

    """
    An abstract class representing an HTTP client.
    """

    def request(
        self,
        method: str,
        uri: str,
        params: Optional[Dict[str, object]] = None,
        data: Optional[Dict[str, object]] = None,
        headers: Optional[Dict[str, str]] = None,
        auth: Optional[Tuple[str, str]] = None,
        timeout: Optional[float] = None,
        allow_redirects: bool = False,
    ) -> TwilioResponse:
        """
        Make an HTTP request.
        """
        raise TwilioException("HttpClient is an abstract class")

    def log_request(self, kwargs: Dict[str, Any]) -> None:
        """
        Logs the HTTP request
        """
        self.logger.info("-- BEGIN Twilio API Request --")

        if kwargs["params"]:
            self.logger.info(
                "{} Request: {}?{}".format(
                    kwargs["method"], kwargs["url"], urlencode(kwargs["params"])
                )
            )
            self.logger.info("Query Params: {}".format(kwargs["params"]))
        else:
            self.logger.info("{} Request: {}".format(kwargs["method"], kwargs["url"]))

        if kwargs["headers"]:
            self.logger.info("Headers:")
            for key, value in kwargs["headers"].items():
                # Do not log authorization headers
                if "authorization" not in key.lower():
                    self.logger.info("{} : {}".format(key, value))

        self.logger.info("-- END Twilio API Request --")

    def log_response(self, status_code: int, response: Response) -> None:
        """
        Logs the HTTP response
        """
        self.logger.info("Response Status Code: {}".format(status_code))
        self.logger.info("Response Headers: {}".format(response.headers))


class AsyncHttpClient(HttpClient):
    """
    An abstract class representing an asynchronous HTTP client.
    """

    async def request(
        self,
        method: str,
        uri: str,
        params: Optional[Dict[str, object]] = None,
        data: Optional[Dict[str, object]] = None,
        headers: Optional[Dict[str, str]] = None,
        auth: Optional[Tuple[str, str]] = None,
        timeout: Optional[float] = None,
        allow_redirects: bool = False,
    ) -> TwilioResponse:
        """
        Make an asynchronous HTTP request.
        """
        raise TwilioException("AsyncHttpClient is an abstract class")
