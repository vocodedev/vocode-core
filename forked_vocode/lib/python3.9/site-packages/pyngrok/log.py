import logging
import shlex
from typing import Optional

__author__ = "Alex Laird"
__copyright__ = "Copyright 2023, Alex Laird"
__version__ = "7.0.0"


class NgrokLog:
    """
    An object containing a parsed log from the ``ngrok`` process.
    """

    def __init__(self,
                 line: str) -> None:
        #: The raw, unparsed log line.
        self.line: str = line.strip()

        #: The log's ISO 8601 timestamp.
        self.t: Optional[str] = None
        #: The log's level.
        self.lvl: str = "NOTSET"
        #: The log's message.
        self.msg: Optional[str] = None
        #: The log's error, if applicable.
        self.err: Optional[str] = None
        #: The URL, if ``obj`` is "web".
        self.addr: Optional[str] = None

        for i in shlex.split(self.line):
            if "=" not in i:
                continue

            key, value = i.split("=", 1)

            if key == "lvl":
                if not value:
                    value = self.lvl

                value = value.upper()
                if value == "CRIT":
                    value = "CRITICAL"
                elif value in ["ERR", "EROR"]:
                    value = "ERROR"
                elif value == "WARN":
                    value = "WARNING"

                if not hasattr(logging, value):
                    value = self.lvl

            setattr(self, key, value)

    def __repr__(self) -> str:
        return "<NgrokLog: t={} lvl={} msg=\"{}\">".format(self.t, self.lvl, self.msg)

    def __str__(self) -> str:  # pragma: no cover
        attrs = [attr for attr in dir(self) if not attr.startswith("_") and getattr(self, attr) is not None]
        attrs.remove("line")

        return " ".join("{}=\"{}\"".format(attr, getattr(self, attr)) for attr in attrs)
