from urllib.parse import urlparse


class Voice:
    auth_type = 'jwt'

    def __init__(self, client):
        self._client = client

    # Creates a new call session
    def create_call(self, params, **kwargs):
        """
        Adding Random From Number Feature for the Voice API,
        if set to `True`, the from number will be randomly selected
        from the pool of numbers available to the application making
        the call.

        :param params is a dictionary that holds the 'from' and 'random_from_number'

        """
        if not params:
            params = kwargs

            key = 'from'
            if key not in params:
                params['random_from_number'] = True

        return self._client.post(
            self._client.api_host(), "/v1/calls", params or kwargs, auth_type=Voice.auth_type
        )

    # Get call history paginated. Pass start and end dates to filter the retrieved information
    def get_calls(self, params=None, **kwargs):
        return self._client.get(
            self._client.api_host(), "/v1/calls", params or kwargs, auth_type=Voice.auth_type
        )

    # Get a single call record by identifier
    def get_call(self, uuid):
        return self._client.get(
            self._client.api_host(), f"/v1/calls/{uuid}", auth_type=Voice.auth_type
        )

    # Update call data using custom ncco
    def update_call(self, uuid, params=None, **kwargs):
        return self._client.put(
            self._client.api_host(),
            f"/v1/calls/{uuid}",
            params or kwargs,
            auth_type=Voice.auth_type,
        )

    # Plays audio streaming into call in progress - stream_url parameter is required
    def send_audio(self, uuid, params=None, **kwargs):
        return self._client.put(
            self._client.api_host(),
            f"/v1/calls/{uuid}/stream",
            params or kwargs,
            auth_type=Voice.auth_type,
        )

    # Play an speech into specified call - text parameter (text to speech) is required
    def send_speech(self, uuid, params=None, **kwargs):
        return self._client.put(
            self._client.api_host(),
            f"/v1/calls/{uuid}/talk",
            params or kwargs,
            auth_type=Voice.auth_type,
        )

    # plays DTMF tones into the specified call
    def send_dtmf(self, uuid, params=None, **kwargs):
        return self._client.put(
            self._client.api_host(),
            f"/v1/calls/{uuid}/dtmf",
            params or kwargs,
            auth_type=Voice.auth_type,
        )

    # Stops audio recently played into specified call
    def stop_audio(self, uuid):
        return self._client.delete(
            self._client.api_host(), f"/v1/calls/{uuid}/stream", auth_type=Voice.auth_type
        )

    # Stop a speech recently played into specified call
    def stop_speech(self, uuid):
        return self._client.delete(
            self._client.api_host(), f"/v1/calls/{uuid}/talk", auth_type=Voice.auth_type
        )

    def get_recording(self, url):
        hostname = urlparse(url).hostname
        headers = self._client.headers
        headers['Authorization'] = self._client._create_jwt_auth_string()
        return self._client.parse(hostname, self._client.session.get(url, headers=headers))
