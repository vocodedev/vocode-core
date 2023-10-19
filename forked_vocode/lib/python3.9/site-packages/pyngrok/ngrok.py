import json
import logging
import os
import socket
import sys
import uuid
from http import HTTPStatus
from typing import Optional, Any, Dict, List, Tuple
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import urlopen, Request

from pyngrok import process, conf, installer
from pyngrok.conf import PyngrokConfig
from pyngrok.exception import PyngrokNgrokHTTPError, PyngrokNgrokURLError, PyngrokSecurityError, PyngrokError
from pyngrok.installer import get_default_config
from pyngrok.process import NgrokProcess

__author__ = "Alex Laird"
__copyright__ = "Copyright 2023, Alex Laird"
__version__ = "7.0.0"

logger = logging.getLogger(__name__)


class NgrokTunnel:
    """
    An object containing information about a ``ngrok`` tunnel.
    """

    def __init__(self,
                 data: Dict[str, Any],
                 pyngrok_config: PyngrokConfig,
                 api_url: Optional[str]) -> None:
        #: The original tunnel data.
        self.data: Dict[str, Any] = data
        #: The ``pyngrok`` configuration to use when interacting with the ``ngrok``.
        self.pyngrok_config: PyngrokConfig = pyngrok_config
        #: The API URL for the ``ngrok`` web interface.
        self.api_url: Optional[str] = api_url

        #: The ID of the tunnel.
        self.id: Optional[str] = data.get("ID", None)
        #: The name of the tunnel.
        self.name: Optional[str] = data.get("name")
        #: The protocol of the tunnel.
        self.proto: Optional[str] = data.get("proto")
        #: The tunnel URI, a relative path that can be used to make requests to the ``ngrok`` web interface.
        self.uri: Optional[str] = data.get("uri")
        #: The public ``ngrok`` URL.
        self.public_url: Optional[str] = data.get("public_url")
        #: The config for the tunnel.
        self.config: Dict[str, Any] = data.get("config", {})
        #: Metrics for `the tunnel <https://ngrok.com/docs/ngrok-agent/api#list-tunnels>`_.
        self.metrics: Dict[str, Any] = data.get("metrics", {})

    def __repr__(self) -> str:
        return "<NgrokTunnel: \"{}\" -> \"{}\">".format(self.public_url, self.config["addr"]) if self.config.get(
            "addr", None) else "<pending Tunnel>"

    def __str__(self) -> str:  # pragma: no cover
        return "NgrokTunnel: \"{}\" -> \"{}\"".format(self.public_url, self.config["addr"]) if self.config.get(
            "addr", None) else "<pending Tunnel>"

    def refresh_metrics(self) -> None:
        """
        Get the latest metrics for the tunnel and update the ``metrics`` variable.
        """
        logger.info("Refreshing metrics for tunnel: {}".format(self.public_url))

        data = api_request("{}{}".format(self.api_url, self.uri), method="GET",
                           timeout=self.pyngrok_config.request_timeout)

        if "metrics" not in data:
            raise PyngrokError("The ngrok API did not return \"metrics\" in the response")

        self.data["metrics"] = data["metrics"]
        self.metrics = self.data["metrics"]


_current_tunnels: Dict[str, NgrokTunnel] = {}


def install_ngrok(pyngrok_config: Optional[PyngrokConfig] = None) -> None:
    """
    Download, install, and initialize ``ngrok`` for the given config. If ``ngrok`` and its default
    config is already installed, calling this method will do nothing.

    :param pyngrok_config: A ``pyngrok`` configuration to use when interacting with the ``ngrok`` binary,
        overriding :func:`~pyngrok.conf.get_default()`.
    """
    if pyngrok_config is None:
        pyngrok_config = conf.get_default()

    if not os.path.exists(pyngrok_config.ngrok_path):
        installer.install_ngrok(pyngrok_config.ngrok_path, ngrok_version=pyngrok_config.ngrok_version)

    config_path = conf.get_config_path(pyngrok_config)

    # Install the config to the requested path
    if not os.path.exists(config_path):
        installer.install_default_config(config_path, ngrok_version=pyngrok_config.ngrok_version)

    # Install the default config, even if we don't need it this time, if it doesn't already exist
    if conf.DEFAULT_NGROK_CONFIG_PATH != config_path and \
            not os.path.exists(conf.DEFAULT_NGROK_CONFIG_PATH):
        installer.install_default_config(conf.DEFAULT_NGROK_CONFIG_PATH, ngrok_version=pyngrok_config.ngrok_version)


def set_auth_token(token: str,
                   pyngrok_config: Optional[PyngrokConfig] = None) -> None:
    """
    Set the ``ngrok`` auth token in the config file, enabling authenticated features (for instance,
    more concurrent tunnels, custom subdomains, etc.).

    If ``ngrok`` is not installed at :class:`~pyngrok.conf.PyngrokConfig`'s ``ngrok_path``, calling this method
    will first download and install ``ngrok``.

    :param token: The auth token to set.
    :param pyngrok_config: A ``pyngrok`` configuration to use when interacting with the ``ngrok`` binary,
        overriding :func:`~pyngrok.conf.get_default()`.
    """
    if pyngrok_config is None:
        pyngrok_config = conf.get_default()

    install_ngrok(pyngrok_config)

    process.set_auth_token(pyngrok_config, token)


def get_ngrok_process(pyngrok_config: Optional[PyngrokConfig] = None) -> NgrokProcess:
    """
    Get the current ``ngrok`` process for the given config's ``ngrok_path``.

    If ``ngrok`` is not installed at :class:`~pyngrok.conf.PyngrokConfig`'s ``ngrok_path``, calling this method
    will first download and install ``ngrok``.

    If ``ngrok`` is not running, calling this method will first start a process with
    :class:`~pyngrok.conf.PyngrokConfig`.

    Use :func:`~pyngrok.process.is_process_running` to check if a process is running without also implicitly
    installing and starting it.

    :param pyngrok_config: A ``pyngrok`` configuration to use when interacting with the ``ngrok`` binary,
        overriding :func:`~pyngrok.conf.get_default()`.
    :return: The ``ngrok`` process.
    """
    if pyngrok_config is None:
        pyngrok_config = conf.get_default()

    install_ngrok(pyngrok_config)

    return process.get_process(pyngrok_config)


def _apply_cloud_edge_to_tunnel(tunnel: NgrokTunnel,
                                pyngrok_config: PyngrokConfig) -> None:
    if not tunnel.public_url and pyngrok_config.api_key and tunnel.id:
        tunnel_response = api_request("https://api.ngrok.com/tunnels/{}".format(tunnel.id), method="GET",
                                      auth=pyngrok_config.api_key)
        if "labels" not in tunnel_response or "edge" not in tunnel_response["labels"]:
            raise PyngrokError(
                "Tunnel {} does not have \"labels\", use a Tunnel configured on Cloud Edge.".format(tunnel.data["ID"]))

        edge = tunnel_response["labels"]["edge"]
        if edge.startswith("edghts_"):
            edges_prefix = "https"
        elif edge.startswith("edgtcp"):
            edges_prefix = "tcp"
        elif edge.startswith("edgtls"):
            edges_prefix = "tls"
        else:
            raise PyngrokError("Unknown Edge prefix: {}.".format(edge))

        edge_response = api_request("https://api.ngrok.com/edges/{}/{}".format(edges_prefix, edge), method="GET",
                                    auth=pyngrok_config.api_key)

        if "hostports" not in edge_response or len(edge_response["hostports"]) < 1:
            raise PyngrokError(
                "No Endpoint is attached to your Cloud Edge {}, login to the ngrok dashboard to attach an Endpoint to your Edge first.".format(
                    edge))

        tunnel.public_url = "{}://{}".format(edges_prefix, edge_response["hostports"][0])
        tunnel.proto = edges_prefix


# When Python <3.9 support is dropped, addr type can be changed to Optional[str|int]
def connect(addr: Optional[str] = None,
            proto: Optional[str] = None,
            name: Optional[str] = None,
            pyngrok_config: Optional[PyngrokConfig] = None,
            **options: Any) -> NgrokTunnel:
    """
    Establish a new ``ngrok`` tunnel for the given protocol to the given port, returning an object representing
    the connected tunnel.

    If a `tunnel definition in ngrok's config file
    <https://ngrok.com/docs/secure-tunnels/ngrok-agent/reference/config/#tunnel-definitions>`_ matches the given
    ``name``, it will be loaded and used to start the tunnel. When ``name`` is ``None`` and a "pyngrok-default" tunnel
    definition exists in ``ngrok``'s config, it will be loaded and use. Any ``kwargs`` passed as ``options`` will
    override properties from the loaded tunnel definition.

    If ``ngrok`` is not installed at :class:`~pyngrok.conf.PyngrokConfig`'s ``ngrok_path``, calling this method
    will first download and install ``ngrok``.

    ``pyngrok`` is compatible with ``ngrok`` v2 and v3, but by default it will install v3. To install v2 instead,
    set ``ngrok_version`` to "v2" in :class:`~pyngrok.conf.PyngrokConfig`:

    If ``ngrok`` is not running, calling this method will first start a process with
    :class:`~pyngrok.conf.PyngrokConfig`.

    .. note::

        ``ngrok`` v2's default behavior for ``http`` when no additional properties are passed is to open *two* tunnels,
        one ``http`` and one ``https``. This method will return a reference to the ``http`` tunnel in this case. If
        only a single tunnel is needed, pass ``bind_tls=True`` and a reference to the ``https`` tunnel will be returned.

    :param addr: The local port to which the tunnel will forward traffic, or a
        `local directory or network address <https://ngrok.com/docs/secure-tunnels/tunnels/http-tunnels#file-url>`_, defaults to "80".
    :param proto: A valid `tunnel protocol
        <https://ngrok.com/docs/secure-tunnels/ngrok-agent/reference/config/#tunnel-definitions>`_, defaults to "http".
    :param name: A friendly name for the tunnel, or the name of a `ngrok tunnel definition <https://ngrok.com/docs/secure-tunnels/ngrok-agent/reference/config/#tunnel-definitions>`_
        to be used.
    :param pyngrok_config: A ``pyngrok`` configuration to use when interacting with the ``ngrok`` binary,
        overriding :func:`~pyngrok.conf.get_default()`.
    :param options: Remaining ``kwargs`` are passed as `configuration for the ngrok
        tunnel <https://ngrok.com/docs/secure-tunnels/ngrok-agent/reference/config/#tunnel-definitions>`_.
    :return: The created ``ngrok`` tunnel.
    """
    if "labels" in options:
        raise PyngrokError("\"labels\" cannot be passed to connect(), define a tunnel definition in the config file.")

    if pyngrok_config is None:
        pyngrok_config = conf.get_default()

    config_path = conf.get_config_path(pyngrok_config)

    if os.path.exists(config_path):
        config = installer.get_ngrok_config(config_path, ngrok_version=pyngrok_config.ngrok_version)
    else:
        config = get_default_config(pyngrok_config.ngrok_version)

    tunnel_definitions = config.get("tunnels", {})
    # If a "pyngrok-default" tunnel definition exists in the ngrok config, use that
    if not name and "pyngrok-default" in tunnel_definitions:
        name = "pyngrok-default"

    # Use a tunnel definition for the given name, if it exists
    if name and name in tunnel_definitions:
        tunnel_definition = tunnel_definitions[name]

        if "labels" in tunnel_definition and "bind_tls" in options:
            raise PyngrokError("\"bind_tls\" cannot be set when \"labels\" is also on the tunnel definition.")

        addr = tunnel_definition.get("addr") if not addr else addr
        proto = tunnel_definition.get("proto") if not proto else proto
        # Use the tunnel definition as the base, but override with any passed in options
        tunnel_definition.update(options)
        options = tunnel_definition

    if "labels" in options and not pyngrok_config.api_key:
        raise PyngrokError(
            "\"PyngrokConfig.api_key\" must be set when \"labels\" is on the tunnel definition.")

    addr = str(addr) if addr else "80"
    # Only apply a default proto label if "labels" isn't defined
    if not proto and "labels" not in options:
        proto = "http"

    if not name:
        if not addr.startswith("file://"):
            name = "{}-{}-{}".format(proto, addr, uuid.uuid4())
        else:
            name = "{}-file-{}".format(proto, uuid.uuid4())

    logger.info("Opening tunnel named: {}".format(name))

    config = {
        "name": name,
        "addr": addr
    }
    options.update(config)

    # Only apply proto when "labels" is not defined
    if "labels" not in options:
        options["proto"] = proto

    # Upgrade legacy parameters, if present
    if pyngrok_config.ngrok_version == "v3":
        if "bind_tls" in options:
            if options.get("bind_tls") is True or options.get("bind_tls") == "true":
                options["schemes"] = ["https"]
            elif not options.get("bind_tls") is not False or options.get("bind_tls") == "false":
                options["schemes"] = ["http"]
            else:
                options["schemes"] = ["http", "https"]

            options.pop("bind_tls")

        if "auth" in options:
            auth = options.get("auth")
            if isinstance(auth, list):
                options["basic_auth"] = auth
            else:
                options["basic_auth"] = [auth]

            options.pop("auth")

    api_url = get_ngrok_process(pyngrok_config).api_url

    logger.debug("Creating tunnel with options: {}".format(options))

    tunnel = NgrokTunnel(api_request("{}/api/tunnels".format(api_url), method="POST", data=options,
                                     timeout=pyngrok_config.request_timeout),
                         pyngrok_config, api_url)

    if pyngrok_config.ngrok_version == "v2" and proto == "http" and options.get("bind_tls", "both") == "both":
        tunnel = NgrokTunnel(api_request("{}{}%20%28http%29".format(api_url, tunnel.uri), method="GET",
                                         timeout=pyngrok_config.request_timeout),
                             pyngrok_config, api_url)

    _apply_cloud_edge_to_tunnel(tunnel, pyngrok_config)

    if tunnel.public_url is None:
        raise PyngrokError(
            "\"public_url\" was not populated for tunnel {}, but is required for pyngrok to function.".format(
                tunnel))

    _current_tunnels[tunnel.public_url] = tunnel

    return tunnel


def disconnect(public_url: str,
               pyngrok_config: Optional[PyngrokConfig] = None) -> None:
    """
    Disconnect the ``ngrok`` tunnel for the given URL, if open.

    :param public_url: The public URL of the tunnel to disconnect.
    :param pyngrok_config: A ``pyngrok`` configuration to use when interacting with the ``ngrok`` binary,
        overriding :func:`~pyngrok.conf.get_default()`.
    """
    if pyngrok_config is None:
        pyngrok_config = conf.get_default()

    # If ngrok is not running, there are no tunnels to disconnect
    if not process.is_process_running(pyngrok_config.ngrok_path):
        return

    api_url = get_ngrok_process(pyngrok_config).api_url

    if public_url not in _current_tunnels:
        get_tunnels(pyngrok_config)

        # One more check, if the given URL is still not in the list of tunnels, it is not active
        if public_url not in _current_tunnels:
            return

    tunnel = _current_tunnels[public_url]

    logger.info("Disconnecting tunnel: {}".format(tunnel.public_url))

    api_request("{}{}".format(api_url, tunnel.uri), method="DELETE",
                timeout=pyngrok_config.request_timeout)

    _current_tunnels.pop(public_url, None)


def get_tunnels(pyngrok_config: Optional[PyngrokConfig] = None) -> List[NgrokTunnel]:
    """
    Get a list of active ``ngrok`` tunnels for the given config's ``ngrok_path``.

    If ``ngrok`` is not installed at :class:`~pyngrok.conf.PyngrokConfig`'s ``ngrok_path``, calling this method
    will first download and install ``ngrok``.

    If ``ngrok`` is not running, calling this method will first start a process with
    :class:`~pyngrok.conf.PyngrokConfig`.

    :param pyngrok_config: A ``pyngrok`` configuration to use when interacting with the ``ngrok`` binary,
        overriding :func:`~pyngrok.conf.get_default()`.
    :return: The active ``ngrok`` tunnels.
    """
    if pyngrok_config is None:
        pyngrok_config = conf.get_default()

    api_url = get_ngrok_process(pyngrok_config).api_url

    _current_tunnels.clear()
    for tunnel in api_request("{}/api/tunnels".format(api_url), method="GET",
                              timeout=pyngrok_config.request_timeout)["tunnels"]:
        ngrok_tunnel = NgrokTunnel(tunnel, pyngrok_config, api_url)
        _apply_cloud_edge_to_tunnel(ngrok_tunnel, pyngrok_config)

        if ngrok_tunnel.public_url is None:
            raise PyngrokError(
                "\"public_url\" was not populated for tunnel {}, but is required for pyngrok to function.".format(
                    ngrok_tunnel))

        _current_tunnels[ngrok_tunnel.public_url] = ngrok_tunnel

    return list(_current_tunnels.values())


def kill(pyngrok_config: Optional[PyngrokConfig] = None) -> None:
    """
    Terminate the ``ngrok`` processes, if running, for the given config's ``ngrok_path``. This method will not
    block, it will just issue a kill request.

    :param pyngrok_config: A ``pyngrok`` configuration to use when interacting with the ``ngrok`` binary,
        overriding :func:`~pyngrok.conf.get_default()`.
    """
    if pyngrok_config is None:
        pyngrok_config = conf.get_default()

    process.kill_process(pyngrok_config.ngrok_path)

    _current_tunnels.clear()


def get_version(pyngrok_config: Optional[PyngrokConfig] = None) -> Tuple[str, str]:
    """
    Get a tuple with the ``ngrok`` and ``pyngrok`` versions.

    :param pyngrok_config: A ``pyngrok`` configuration to use when interacting with the ``ngrok`` binary,
        overriding :func:`~pyngrok.conf.get_default()`.
    :return: A tuple of ``(ngrok_version, pyngrok_version)``.
    """
    if pyngrok_config is None:
        pyngrok_config = conf.get_default()

    ngrok_version = process.capture_run_process(pyngrok_config.ngrok_path, ["--version"]).split("version ")[1]

    return ngrok_version, __version__


def update(pyngrok_config: Optional[PyngrokConfig] = None) -> str:
    """
    Update ``ngrok`` for the given config's ``ngrok_path``, if an update is available.

    :param pyngrok_config: A ``pyngrok`` configuration to use when interacting with the ``ngrok`` binary,
        overriding :func:`~pyngrok.conf.get_default()`.
    :return: The result from the ``ngrok`` update.
    """
    if pyngrok_config is None:
        pyngrok_config = conf.get_default()

    return process.capture_run_process(pyngrok_config.ngrok_path, ["update"])


def api_request(url: str,
                method: str = "GET",
                data: Optional[Dict[str, Any]] = None,
                params: Optional[Dict[str, Any]] = None,
                timeout: float = 4,
                auth: Optional[str] = None) -> Dict[str, Any]:
    """
    Invoke an API request to the given URL, returning JSON data from the response.

    One use for this method is making requests to ``ngrok`` tunnels:

    .. code-block:: python

        from pyngrok import ngrok

        public_url = ngrok.connect()
        response = ngrok.api_request("{}/some-route".format(public_url),
                                     method="POST", data={"foo": "bar"})

    Another is making requests to the ``ngrok`` API itself:

    .. code-block:: python

        from pyngrok import ngrok

        api_url = ngrok.get_ngrok_process().api_url
        response = ngrok.api_request("{}/api/requests/http".format(api_url),
                                     params={"tunnel_name": "foo"})

    :param url: The request URL.
    :param method: The HTTP method.
    :param data: The request body.
    :param params: The URL parameters.
    :param timeout: The request timeout, in seconds.
    :param auth: Set as Bearer for an Authorization header.
    :return: The response from the request.
    """
    if params is None:
        params = {}

    if not url.lower().startswith("http"):
        raise PyngrokSecurityError("URL must start with \"http\": {}".format(url))

    encoded_data = json.dumps(data).encode("utf-8") if data else None

    if params:
        url += "?{}".format(urlencode([(x, params[x]) for x in params]))

    request = Request(url, method=method.upper())
    request.add_header("Content-Type", "application/json")
    if auth:
        request.add_header("Ngrok-Version", "2")
        request.add_header("Authorization", "Bearer {}".format(auth))

    logger.debug("Making {} request to {} with data: {}".format(method, url, data))

    try:
        response = urlopen(request, encoded_data, timeout)
        response_data = response.read().decode("utf-8")

        status_code = response.getcode()
        logger.debug("Response {}: {}".format(status_code, response_data.strip()))

        if str(status_code)[0] != "2":
            raise PyngrokNgrokHTTPError("ngrok client API returned {}: {}".format(status_code, response_data), url,
                                        status_code, None, request.headers, response_data)
        elif status_code == HTTPStatus.NO_CONTENT:
            return {}

        return json.loads(response_data)
    except socket.timeout:
        raise PyngrokNgrokURLError("ngrok client exception, URLError: timed out", "timed out")
    except HTTPError as e:
        response_data = e.read().decode("utf-8")

        status_code = e.getcode()
        logger.debug("Response {}: {}".format(status_code, response_data.strip()))

        raise PyngrokNgrokHTTPError("ngrok client exception, API returned {}: {}".format(status_code, response_data),
                                    e.url,
                                    status_code, e.reason, e.headers, response_data)
    except URLError as e:
        raise PyngrokNgrokURLError("ngrok client exception, URLError: {}".format(e.reason), e.reason)


def run(args: Optional[List[str]] = None,
        pyngrok_config: Optional[PyngrokConfig] = None) -> None:
    """
    Ensure ``ngrok`` is installed at the default path, then call :func:`~pyngrok.process.run_process`.

    This method is meant for interacting with ``ngrok`` from the command line and is not necessarily
    compatible with non-blocking API methods. For that, use :mod:`~pyngrok.ngrok`'s interface methods (like
    :func:`~pyngrok.ngrok.connect`), or use :func:`~pyngrok.process.get_process`.

    :param args: Arguments to be passed to the ``ngrok`` process.
    :param pyngrok_config: A ``pyngrok`` configuration to use when interacting with the ``ngrok`` binary,
        overriding :func:`~pyngrok.conf.get_default()`.
    """
    if args is None:
        args = []
    if pyngrok_config is None:
        pyngrok_config = conf.get_default()

    install_ngrok(pyngrok_config)

    process.run_process(pyngrok_config.ngrok_path, args)


def main() -> None:
    """
    Entry point for the package's ``console_scripts``. This initializes a call from the command
    line and invokes :func:`~pyngrok.ngrok.run`.

    This method is meant for interacting with ``ngrok`` from the command line and is not necessarily
    compatible with non-blocking API methods. For that, use :mod:`~pyngrok.ngrok`'s interface methods (like
    :func:`~pyngrok.ngrok.connect`), or use :func:`~pyngrok.process.get_process`.
    """
    run(sys.argv[1:])

    if len(sys.argv) == 1 or len(sys.argv) == 2 and sys.argv[1].lstrip("-").lstrip("-") == "help":
        print("\nPYNGROK VERSION:\n   {}".format(__version__))
    elif len(sys.argv) == 2 and sys.argv[1].lstrip("-").lstrip("-") in ["v", "version"]:
        print("pyngrok version {}".format(__version__))


if __name__ == "__main__":
    main()
