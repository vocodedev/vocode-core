import json
import logging
import sys

from loguru import logger
from loguru._handler import Handler

from vocode import get_serialized_ctx_wrappers


def _patched_serialize_record(text: str, record: dict) -> str:
    """
    This function takes a text string and a record dictionary as input and returns a serialized
    string representation of the record.

    The record dictionary is expected to contain various keys related to logging information such as
    'level', 'time', 'elapsed', 'exception', 'extra', 'file', 'function', 'line', 'message',
    'module', 'name', 'process', 'thread'. Each key's value is processed and added to a new
    dictionary 'serializable'.

    If the 'exception' key in the record is not None, it is further processed to extract 'type',
    'value', and 'traceback' information.

    The 'serializable' dictionary is then converted to a JSON string using json.dumps. The 'default'
    parameter is set to str to convert any non-serializable types to string. The 'ensure_ascii'
    parameter is set to False so that the function can output non-ASCII characters as they are.

    The function finally returns the serialized string with a newline character appended at the end.

    Args:
        text (str): A text string. record (dict): A dictionary containing logging information.

    Returns:
        str: A serialized string representation of the record dictionary.
    """
    exception = record["exception"]

    if exception is not None:
        exception = {
            "type": None if exception.type is None else exception.type.__name__,
            "value": exception.value,
            "traceback": bool(exception.traceback),
        }

    serializable = {
        "severity": record["level"].name,
        "text": text,
        "timestamp": record["time"].timestamp(),
        "elapsed": {
            "repr": record["elapsed"],
            "seconds": record["elapsed"].total_seconds(),
        },
        "exception": exception,
        "ctx": get_serialized_ctx_wrappers(),
        "extra": record["extra"],
        "file": {"name": record["file"].name, "path": record["file"].path},
        "function": record["function"],
        "level": {
            "icon": record["level"].icon,
            "name": record["level"].name,
            "no": record["level"].no,
        },
        "line": record["line"],
        "message": record["message"],
        "module": record["module"],
        "name": record["name"],
        "process": {"id": record["process"].id, "name": record["process"].name},
        "thread": {"id": record["thread"].id, "name": record["thread"].name},
        "time": {"repr": record["time"], "timestamp": record["time"].timestamp()},
    }

    return json.dumps(serializable, default=str, ensure_ascii=False) + "\n"


Handler._serialize_record = staticmethod(_patched_serialize_record)  # type: ignore


class InterceptHandler(logging.Handler):
    """
    Default handler from examples in loguru documentation.

    This handler intercepts all log requests and
    passes them to loguru.

    For more info see:
    https://loguru.readthedocs.io/en/stable/overview.html#entirely-compatible-with-standard-logging
    """

    def emit(self, record: logging.LogRecord) -> None:  # pragma: no cover
        """
        Propagates logs to loguru.

        :param record: record to log.
        """
        try:
            level: str | int = logger.level(record.levelname).name
        except ValueError:
            level = record.levelno

        # Find caller from where originated the logged message
        frame, depth = logging.currentframe(), 2
        while (
            frame.f_code.co_filename == logging.__file__
            or frame.f_code.co_filename == __file__
            or "sentry_sdk/integrations" in frame.f_code.co_filename
        ):
            frame = frame.f_back  # type: ignore
            depth += 1
        logger.opt(depth=depth, exception=record.exc_info).log(
            level,
            record.getMessage(),
        )


def configure_intercepter() -> None:
    """
    Configures the logging system to intercept log messages.

    This function sets up an InterceptHandler instance as the main handler for the root logger.
    It sets the logging level to INFO, meaning that all messages with severity INFO and above will be handled.

    It then iterates over all the loggers in the logging system. If a logger's name starts with "uvicorn.",
    it removes all handlers from that logger. This is done to prevent uvicorn's default logging configuration
    from interfering with our custom configuration.

    Finally, it sets the InterceptHandler instance as the sole handler for the "uvicorn" and "uvicorn.access" loggers.
    This ensures that all log messages from uvicorn and its access logger are intercepted by our custom handler.
    """
    intercept_handler = InterceptHandler()
    logging.basicConfig(handlers=[intercept_handler], level=logging.INFO)

    for logger_name in logging.root.manager.loggerDict:
        if logger_name.startswith("uvicorn."):
            logging.getLogger(logger_name).handlers = []

    logging.getLogger("uvicorn").handlers = [intercept_handler]
    logging.getLogger("uvicorn.access").handlers = [intercept_handler]


def configure_pretty_logging() -> None:
    """
    Configures the logging system to output pretty logs.

    This function enables the 'vocode' logger, sets up an intercept handler to
    capture logs from the standard logging module, removes all existing handlers
    from the 'loguru' logger, and adds a new handler that outputs to stdout with
    pretty formatting (colored, not serialized, no backtrace or diagnosis information).
    """
    logger.enable("vocode")

    configure_intercepter()

    logger.remove()
    logger.add(
        sys.stdout,
        level=logging.DEBUG,
        backtrace=False,
        diagnose=False,
        serialize=False,
        colorize=True,
    )


def configure_json_logging() -> None:
    """
    Configures the logging system to output logs in JSON format.

    This function enables the 'vocode' logger, sets up an intercept handler to
    capture logs from the standard logging module, removes all existing handlers
    from the 'loguru' logger, and adds a new handler that outputs to stdout with
    JSON formatting (serialized, no backtrace or diagnosis information).
    """
    logger.enable("vocode")

    configure_intercepter()

    logger.remove()
    logger.add(
        sys.stdout,
        format="{message}",
        level=logging.DEBUG,
        backtrace=False,
        diagnose=False,
        serialize=True,
    )
