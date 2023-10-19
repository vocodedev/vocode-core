import atexit
import logging
import os
import subprocess
import threading
import time
from http import HTTPStatus
from typing import Dict, List, Optional, Any
from urllib.request import Request, urlopen

import yaml

from pyngrok import conf, installer
from pyngrok.conf import PyngrokConfig
from pyngrok.exception import PyngrokNgrokError, PyngrokSecurityError, PyngrokError
from pyngrok.installer import SUPPORTED_NGROK_VERSIONS
from pyngrok.log import NgrokLog

__author__ = "Alex Laird"
__copyright__ = "Copyright 2023, Alex Laird"
__version__ = "7.0.0"

logger = logging.getLogger(__name__)
ngrok_logger = logging.getLogger("{}.ngrok".format(__name__))


class NgrokProcess:
    """
    An object containing information about the ``ngrok`` process.
    """

    def __init__(self,
                 proc: subprocess.Popen,
                 pyngrok_config: PyngrokConfig) -> None:
        #: The child process that is running ``ngrok``.
        self.proc: subprocess.Popen = proc
        #: The ``pyngrok`` configuration to use with ``ngrok``.
        self.pyngrok_config: PyngrokConfig = pyngrok_config

        #: The API URL for the ``ngrok`` web interface.
        self.api_url: Optional[str] = None
        #: A list of the most recent logs from ``ngrok``, limited in size to ``max_logs``.
        self.logs: List[NgrokLog] = []
        #: If ``ngrok`` startup fails, this will be the log of the failure.
        self.startup_error: Optional[str] = None

        self._tunnel_started = False
        self._client_connected = False
        self._monitor_thread: Optional[threading.Thread] = None

    def __repr__(self) -> str:
        return "<NgrokProcess: \"{}\">".format(self.api_url)

    def __str__(self) -> str:  # pragma: no cover
        return "NgrokProcess: \"{}\"".format(self.api_url)

    @staticmethod
    def _line_has_error(log: NgrokLog) -> bool:
        return log.lvl in ["ERROR", "CRITICAL"]

    def _log_startup_line(self, line: str) -> Optional[NgrokLog]:
        """
        Parse the given startup log line and use it to manage the startup state
        of the ``ngrok`` process.

        :param line: The line to be parsed and logged.
        :return: The parsed log.
        """
        log = self._log_line(line)

        if log is None:
            return None
        elif self._line_has_error(log):
            self.startup_error = log.err
        elif log.msg:
            # Log ngrok startup states as they come in
            if "starting web service" in log.msg and log.addr is not None:
                self.api_url = "http://{}".format(log.addr)
            elif "tunnel session started" in log.msg:
                self._tunnel_started = True
            elif "client session established" in log.msg:
                self._client_connected = True

        return log

    def _log_line(self, line: str) -> Optional[NgrokLog]:
        """
        Parse, log, and emit (if ``log_event_callback`` in :class:`~pyngrok.conf.PyngrokConfig` is registered) the
        given log line.

        :param line: The line to be processed.
        :return: The parsed log.
        """
        log = NgrokLog(line)

        if log.line == "":
            return None

        ngrok_logger.log(getattr(logging, log.lvl), log.line)
        self.logs.append(log)
        if len(self.logs) > self.pyngrok_config.max_logs:
            self.logs.pop(0)

        if self.pyngrok_config.log_event_callback is not None:
            self.pyngrok_config.log_event_callback(log)

        return log

    def healthy(self) -> bool:
        """
        Check whether the ``ngrok`` process has finished starting up and is in a running, healthy state.

        :return: ``True`` if the ``ngrok`` process is started, running, and healthy.
        """
        if self.api_url is None or \
                not self._tunnel_started or \
                not self._client_connected:
            return False

        if not self.api_url.lower().startswith("http"):
            raise PyngrokSecurityError("URL must start with \"http\": {}".format(self.api_url))

        # Ensure the process is available for requests before registering it as healthy
        request = Request("{}/api/tunnels".format(self.api_url))
        response = urlopen(request)
        if response.getcode() != HTTPStatus.OK:
            return False

        return self.proc.poll() is None

    def _monitor_process(self) -> None:
        thread = threading.current_thread()

        thread.alive = True
        while thread.alive and self.proc.poll() is None:
            if self.proc.stdout is None:
                logger.debug("No stdout when monitoring the process, this may or may not be an issue")
                continue

            self._log_line(self.proc.stdout.readline())

        self._monitor_thread = None

    def start_monitor_thread(self) -> None:
        """
        Start a thread that will monitor the ``ngrok`` process and its logs until it completes.

        If a monitor thread is already running, nothing will be done.
        """
        if self._monitor_thread is None:
            logger.debug("Monitor thread will be started")

            self._monitor_thread = threading.Thread(target=self._monitor_process)
            self._monitor_thread.daemon = True
            self._monitor_thread.start()

    def stop_monitor_thread(self) -> None:
        """
        Set the monitor thread to stop monitoring the ``ngrok`` process after the next log event. This will not
        necessarily terminate the thread immediately, as the thread may currently be idle, rather it sets a flag
        on the thread telling it to terminate the next time it wakes up.

        This has no impact on the ``ngrok`` process itself, only ``pyngrok``'s monitor of the process and
        its logs.
        """
        if self._monitor_thread is not None:
            logger.debug("Monitor thread will be stopped")

            self._monitor_thread.alive = False


def set_auth_token(pyngrok_config: PyngrokConfig,
                   token: str) -> None:
    """
    Set the ``ngrok`` auth token in the config file, enabling authenticated features (for instance,
    more concurrent tunnels, custom subdomains, etc.).

    :param pyngrok_config: The ``pyngrok`` configuration to use when interacting with the ``ngrok`` binary.
    :param token: The auth token to set.
    """
    if pyngrok_config.ngrok_version == "v2":
        start = [pyngrok_config.ngrok_path, "authtoken", token, "--log=stdout"]
    elif pyngrok_config.ngrok_version == "v3":
        start = [pyngrok_config.ngrok_path, "config", "add-authtoken", token, "--log=stdout"]
    else:
        raise PyngrokError("\"ngrok_version\" must be a supported version: {}".format(SUPPORTED_NGROK_VERSIONS))

    if pyngrok_config.config_path:
        logger.info("Updating authtoken for \"config_path\": {}".format(pyngrok_config.config_path))
        start.append("--config={}".format(pyngrok_config.config_path))
    else:
        logger.info(
            "Updating authtoken for default \"config_path\" of \"ngrok_path\": {}".format(pyngrok_config.ngrok_path))

    result = str(subprocess.check_output(start))

    if "Authtoken saved" not in result:
        raise PyngrokNgrokError("An error occurred when saving the auth token: {}".format(result))


def is_process_running(ngrok_path: str) -> bool:
    """
    Check if the ``ngrok`` process is currently running.

    :param ngrok_path: The path to the ``ngrok`` binary.
    :return: ``True`` if ``ngrok`` is running from the given path.
    """
    if ngrok_path in _current_processes:
        # Ensure the process is still running and hasn't been killed externally, otherwise cleanup
        if _current_processes[ngrok_path].proc.poll() is None:
            return True
        else:
            logger.debug(
                "Removing stale process for \"ngrok_path\" {}".format(ngrok_path))

            _current_processes.pop(ngrok_path, None)

    return False


def get_process(pyngrok_config: PyngrokConfig) -> NgrokProcess:
    """
    Get the current ``ngrok`` process for the given config's ``ngrok_path``.

    If ``ngrok`` is not running, calling this method will first start a process with
    :class:`~pyngrok.conf.PyngrokConfig`.

    :param pyngrok_config: The ``pyngrok`` configuration to use when interacting with the ``ngrok`` binary.
    :return: The ``ngrok`` process.
    """
    if is_process_running(pyngrok_config.ngrok_path):
        return _current_processes[pyngrok_config.ngrok_path]

    return _start_process(pyngrok_config)


def kill_process(ngrok_path: str) -> None:
    """
    Terminate the ``ngrok`` processes, if running, for the given path. This method will not block, it will just
    issue a kill request.

    :param ngrok_path: The path to the ``ngrok`` binary.
    """
    if is_process_running(ngrok_path):
        ngrok_process = _current_processes[ngrok_path]

        logger.info("Killing ngrok process: {}".format(ngrok_process.proc.pid))

        try:
            ngrok_process.proc.kill()
            ngrok_process.proc.wait()
        except OSError as e:  # pragma: no cover
            # If the process was already killed, nothing to do but cleanup state
            if e.errno != 3:
                raise e

        _current_processes.pop(ngrok_path, None)
    else:
        logger.debug("\"ngrok_path\" {} is not running a process".format(ngrok_path))


def run_process(ngrok_path: str, args: List[str]) -> None:
    """
    Start a blocking ``ngrok`` process with the binary at the given path and the passed args.

    This method is meant for invoking ``ngrok`` directly (for instance, from the command line) and is not
    necessarily compatible with non-blocking API methods. For that, use :func:`~pyngrok.process.get_process`.

    :param ngrok_path: The path to the ``ngrok`` binary.
    :param args: The args to pass to ``ngrok``.
    """
    _validate_path(ngrok_path)

    start = [ngrok_path] + args
    subprocess.call(start)


def capture_run_process(ngrok_path: str, args: List[str]) -> str:
    """
    Start a blocking ``ngrok`` process with the binary at the given path and the passed args. When the process
    returns, so will this method, and the captured output from the process along with it.

    This method is meant for invoking ``ngrok`` directly (for instance, from the command line) and is not
    necessarily compatible with non-blocking API methods. For that, use :func:`~pyngrok.process.get_process`.

    :param ngrok_path: The path to the ``ngrok`` binary.
    :param args: The args to pass to ``ngrok``.
    :return: The output from the process.
    """
    _validate_path(ngrok_path)

    start = [ngrok_path] + args
    output = subprocess.check_output(start)

    return output.decode("utf-8").strip()


def _validate_path(ngrok_path: str) -> None:
    """
    Validate the given path exists, is a ``ngrok`` binary, and is ready to be started, otherwise raise a
    relevant exception.

    :param ngrok_path: The path to the ``ngrok`` binary.
    """
    if not os.path.exists(ngrok_path):
        raise PyngrokNgrokError(
            "ngrok binary was not found. Be sure to call \"ngrok.install_ngrok()\" first for "
            "\"ngrok_path\": {}".format(ngrok_path))

    if ngrok_path in _current_processes:
        raise PyngrokNgrokError("ngrok is already running for the \"ngrok_path\": {}".format(ngrok_path))


def _validate_config(config_path: str) -> None:
    with open(config_path, "r") as config_file:
        config = yaml.safe_load(config_file)

    if config is not None:
        installer.validate_config(config)


def _terminate_process(process: subprocess.Popen) -> None:
    if process is None:
        return

    try:
        process.terminate()
    except OSError:  # pragma: no cover
        logger.debug("ngrok process already terminated: {}".format(process.pid))


def _start_process(pyngrok_config: PyngrokConfig) -> NgrokProcess:
    """
    Start a ``ngrok`` process with no tunnels. This will start the ``ngrok`` web interface, against
    which HTTP requests can be made to create, interact with, and destroy tunnels.

    :param pyngrok_config: The ``pyngrok`` configuration to use when interacting with the ``ngrok`` binary.
    :return: The ``ngrok`` process.
    """
    config_path = conf.get_config_path(pyngrok_config)

    _validate_path(pyngrok_config.ngrok_path)
    _validate_config(config_path)

    start = [pyngrok_config.ngrok_path, "start", "--none", "--log=stdout"]
    if pyngrok_config.config_path:
        logger.info("Starting ngrok with config file: {}".format(pyngrok_config.config_path))
        start.append("--config={}".format(pyngrok_config.config_path))
    if pyngrok_config.auth_token:
        logger.info("Overriding default auth token")
        start.append("--authtoken={}".format(pyngrok_config.auth_token))
    if pyngrok_config.region:
        logger.info("Starting ngrok in region: {}".format(pyngrok_config.region))
        start.append("--region={}".format(pyngrok_config.region))

    popen_kwargs: Dict[str, Any] = {"stdout": subprocess.PIPE, "universal_newlines": True}
    if os.name == "posix":
        popen_kwargs.update(start_new_session=pyngrok_config.start_new_session)
    elif pyngrok_config.start_new_session:
        logger.warning("Ignoring start_new_session=True, which requires POSIX")
    proc = subprocess.Popen(start, **popen_kwargs)
    atexit.register(_terminate_process, proc)

    logger.debug("ngrok process starting with PID: {}".format(proc.pid))

    ngrok_process = NgrokProcess(proc, pyngrok_config)
    _current_processes[pyngrok_config.ngrok_path] = ngrok_process

    timeout = time.time() + pyngrok_config.startup_timeout
    while time.time() < timeout:
        if proc.stdout is None:
            logger.debug("No stdout when starting the process, this may or may not be an issue")
            break

        line = proc.stdout.readline()
        ngrok_process._log_startup_line(line)

        if ngrok_process.healthy():
            logger.debug("ngrok process has started with API URL: {}".format(ngrok_process.api_url))

            ngrok_process.startup_error = None

            if pyngrok_config.monitor_thread:
                ngrok_process.start_monitor_thread()

            break
        elif ngrok_process.proc.poll() is not None:
            break

    if not ngrok_process.healthy():
        # If the process did not come up in a healthy state, clean up the state
        kill_process(pyngrok_config.ngrok_path)

        if ngrok_process.startup_error is not None:
            raise PyngrokNgrokError("The ngrok process errored on start: {}.".format(ngrok_process.startup_error),
                                    ngrok_process.logs,
                                    ngrok_process.startup_error)
        else:
            raise PyngrokNgrokError("The ngrok process was unable to start.", ngrok_process.logs)

    return ngrok_process


_current_processes: Dict[str, NgrokProcess] = {}
