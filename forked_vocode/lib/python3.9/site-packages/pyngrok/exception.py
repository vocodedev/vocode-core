from typing import Any, Optional, List

from pyngrok.log import NgrokLog

__author__ = "Alex Laird"
__copyright__ = "Copyright 2023, Alex Laird"
__version__ = "7.0.0"


class PyngrokError(Exception):
    """
    Raised when a general ``pyngrok`` error has occurred.
    """
    pass


class PyngrokSecurityError(PyngrokError):
    """
    Raised when a ``pyngrok`` security error has occurred.
    """
    pass


class PyngrokNgrokInstallError(PyngrokError):
    """
    Raised when an error has occurred while downloading and installing the ``ngrok`` binary.
    """
    pass


class PyngrokNgrokError(PyngrokError):
    """
    Raised when an error occurs interacting directly with the ``ngrok`` binary.
    """

    def __init__(self,
                 error: str,
                 ngrok_logs: Optional[List[NgrokLog]] = None,
                 ngrok_error: Optional[str] = None) -> None:
        super(PyngrokNgrokError, self).__init__(error)

        #: The ``ngrok`` logs, which may be useful for debugging the error.
        self.ngrok_logs: List[NgrokLog] = ngrok_logs if ngrok_logs else []
        #: The error that caused the ``ngrok`` process to fail.
        self.ngrok_error: Optional[str] = ngrok_error


class PyngrokNgrokHTTPError(PyngrokNgrokError):
    """
    Raised when an error occurs making a request to the ``ngrok`` web interface. The ``body``
    contains the error response received from ``ngrok``.
    """

    # When Python <3.9 support is dropped, headers type can be changed to Dict[str, str]|MutableMapping[str, str]|Any
    def __init__(self,
                 error: str,
                 url: str,
                 status_code: int,
                 message: Optional[str],
                 headers: Any,
                 body: str) -> None:
        super(PyngrokNgrokHTTPError, self).__init__(error)

        #: The request URL that failed.
        self.url: str = url
        #: The response status code from ``ngrok``.
        self.status_code: int = status_code
        #: The response message from ``ngrok``.
        self.message: Optional[str] = message
        #: The request headers sent to ``ngrok``.
        self.headers: Any = headers
        #: The response body from ``ngrok``.
        self.body: str = body


class PyngrokNgrokURLError(PyngrokNgrokError):
    """
    Raised when an error occurs when trying to initiate an API request.
    """

    # When Python <3.9 support is dropped, reason type can be changed to str|BaseException
    def __init__(self,
                 error: str,
                 reason: Any) -> None:
        super(PyngrokNgrokURLError, self).__init__(error)

        #: The reason for the URL error.
        self.reason: Any = reason
