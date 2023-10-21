import logging
from typing import Dict, Optional, Tuple

from requests import Request, Session, hooks
from requests.adapters import HTTPAdapter

from twilio.http import HttpClient
from twilio.http.request import Request as TwilioRequest
from twilio.http.response import Response

_logger = logging.getLogger("twilio.http_client")


class TwilioHttpClient(HttpClient):
    """
    General purpose HTTP Client for interacting with the Twilio API
    """

    def __init__(
        self,
        pool_connections: bool = True,
        request_hooks: Optional[Dict[str, object]] = None,
        timeout: Optional[float] = None,
        logger: logging.Logger = _logger,
        proxy: Optional[Dict[str, str]] = None,
        max_retries: Optional[int] = None,
    ):
        """
        Constructor for the TwilioHttpClient

        :param pool_connections
        :param request_hooks
        :param timeout: Timeout for the requests.
                        Timeout should never be zero (0) or less.
        :param logger
        :param proxy: Http proxy for the requests session
        :param max_retries: Maximum number of retries each request should attempt
        """
        super().__init__(logger, False, timeout)
        self.session = Session() if pool_connections else None
        if self.session and max_retries is not None:
            self.session.mount("https://", HTTPAdapter(max_retries=max_retries))

        self.request_hooks = request_hooks or hooks.default_hooks()
        self.proxy = proxy if proxy else {}

    def request(
        self,
        method: str,
        url: str,
        params: Optional[Dict[str, object]] = None,
        data: Optional[Dict[str, object]] = None,
        headers: Optional[Dict[str, str]] = None,
        auth: Optional[Tuple[str, str]] = None,
        timeout: Optional[float] = None,
        allow_redirects: bool = False,
    ) -> Response:
        """
        Make an HTTP Request with parameters provided.

        :param method: The HTTP method to use
        :param url: The URL to request
        :param params: Query parameters to append to the URL
        :param data: Parameters to go in the body of the HTTP request
        :param headers: HTTP Headers to send with the request
        :param auth: Basic Auth arguments
        :param timeout: Socket/Read timeout for the request
        :param allow_redirects: Whether or not to allow redirects
        See the requests documentation for explanation of all these parameters

        :return: An http response
        """
        if timeout is None:
            timeout = self.timeout
        elif timeout <= 0:
            raise ValueError(timeout)

        kwargs = {
            "method": method.upper(),
            "url": url,
            "params": params,
            "data": data,
            "headers": headers,
            "auth": auth,
            "hooks": self.request_hooks,
        }

        self.log_request(kwargs)

        self._test_only_last_response = None
        session = self.session or Session()
        request = Request(**kwargs)
        self._test_only_last_request = TwilioRequest(**kwargs)

        prepped_request = session.prepare_request(request)

        settings = session.merge_environment_settings(
            prepped_request.url, self.proxy, None, None, None
        )

        response = session.send(
            prepped_request,
            allow_redirects=allow_redirects,
            timeout=timeout,
            **settings
        )

        self.log_response(response.status_code, response)

        self._test_only_last_response = Response(
            int(response.status_code), response.text, response.headers
        )

        return self._test_only_last_response
