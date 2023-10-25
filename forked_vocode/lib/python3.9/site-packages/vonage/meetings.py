from .errors import MeetingsError

from typing_extensions import Literal
import logging
import requests


logger = logging.getLogger("vonage")


class Meetings:
    """Class containing methods used to create and manage meetings using the Meetings API."""

    _auth_type = 'jwt'

    def __init__(self, client):
        self._client = client
        self._meetings_api_host = client.meetings_api_host()

    def list_rooms(self, page_size: str = 20, start_id: str = None, end_id: str = None):
        params = Meetings.set_start_and_end_params(start_id, end_id)
        params['page_size'] = page_size
        return self._client.get(
            self._meetings_api_host, '/rooms', params, auth_type=Meetings._auth_type
        )

    def create_room(self, params: dict = {}):
        if 'display_name' not in params:
            raise MeetingsError(
                'You must include a value for display_name as a field in the params dict when creating a meeting room.'
            )
        if 'type' not in params or 'type' in params and params['type'] != 'long_term':
            if 'expires_at' in params:
                raise MeetingsError('Cannot set "expires_at" for an instant room.')
        elif params['type'] == 'long_term' and 'expires_at' not in params:
            raise MeetingsError('You must set a value for "expires_at" for a long-term room.')

        return self._client.post(
            self._meetings_api_host, '/rooms', params, auth_type=Meetings._auth_type
        )

    def get_room(self, room_id: str):
        return self._client.get(
            self._meetings_api_host, f'/rooms/{room_id}', auth_type=Meetings._auth_type
        )

    def update_room(self, room_id: str, params: dict):
        return self._client.patch(
            self._meetings_api_host, f'/rooms/{room_id}', params, auth_type=Meetings._auth_type
        )

    def add_theme_to_room(self, room_id: str, theme_id: str):
        params = {'update_details': {'theme_id': theme_id}}
        return self._client.patch(
            self._meetings_api_host, f'/rooms/{room_id}', params, auth_type=Meetings._auth_type
        )

    def get_recording(self, recording_id: str):
        return self._client.get(
            self._meetings_api_host, f'/recordings/{recording_id}', auth_type=Meetings._auth_type
        )

    def delete_recording(self, recording_id: str):
        return self._client.delete(
            self._meetings_api_host, f'/recordings/{recording_id}', auth_type=Meetings._auth_type
        )

    def get_session_recordings(self, session_id: str):
        return self._client.get(
            self._meetings_api_host,
            f'/sessions/{session_id}/recordings',
            auth_type=Meetings._auth_type,
        )

    def list_dial_in_numbers(self):
        return self._client.get(
            self._meetings_api_host, '/dial-in-numbers', auth_type=Meetings._auth_type
        )

    def list_themes(self):
        return self._client.get(self._meetings_api_host, '/themes', auth_type=Meetings._auth_type)

    def create_theme(self, params: dict):
        if 'main_color' not in params or 'brand_text' not in params:
            raise MeetingsError('Values for "main_color" and "brand_text" must be specified')

        return self._client.post(
            self._meetings_api_host, '/themes', params, auth_type=Meetings._auth_type
        )

    def get_theme(self, theme_id: str):
        return self._client.get(
            self._meetings_api_host, f'/themes/{theme_id}', auth_type=Meetings._auth_type
        )

    def delete_theme(self, theme_id: str, force: bool = False):
        params = {'force': force}
        return self._client.delete(
            self._meetings_api_host,
            f'/themes/{theme_id}',
            params=params,
            auth_type=Meetings._auth_type,
        )

    def update_theme(self, theme_id: str, params: dict):
        return self._client.patch(
            self._meetings_api_host, f'/themes/{theme_id}', params, auth_type=Meetings._auth_type
        )

    def list_rooms_with_theme_id(
        self, theme_id: str, page_size: int = 20, start_id: str = None, end_id: str = None
    ):
        params = Meetings.set_start_and_end_params(start_id, end_id)
        params['page_size'] = page_size

        return self._client.get(
            self._meetings_api_host,
            f'/themes/{theme_id}/rooms',
            params,
            auth_type=Meetings._auth_type,
        )

    def update_application_theme(self, theme_id: str):
        params = {'update_details': {'default_theme_id': theme_id}}
        return self._client.patch(
            self._meetings_api_host, '/applications', params, auth_type=Meetings._auth_type
        )

    def upload_logo_to_theme(
        self, theme_id: str, path_to_image: str, logo_type: Literal['white', 'colored', 'favicon']
    ):
        params = self._get_logo_upload_url(logo_type)
        self._upload_to_aws(params, path_to_image)
        self._add_logo_to_theme(theme_id, params['fields']['key'])
        return f'Logo upload to theme: {theme_id} was successful.'

    def _get_logo_upload_url(self, logo_type):
        upload_urls = self._client.get(
            self._meetings_api_host, '/themes/logos-upload-urls', auth_type=Meetings._auth_type
        )
        for url_object in upload_urls:
            if url_object['fields']['logoType'] == logo_type:
                return url_object
        raise MeetingsError('Cannot find the upload URL for the specified logo type.')

    def _upload_to_aws(self, params, path_to_image):
        form = {**params['fields'], 'file': open(path_to_image, 'rb')}

        logger.debug(f"POST to {params['url']} to upload file {path_to_image}")
        logo_upload = requests.post(
            url=params['url'],
            files=form,
        )
        if logo_upload.status_code != 204:
            raise MeetingsError(f'Logo upload process failed. {logo_upload.content}')

    def _add_logo_to_theme(self, theme_id: str, key: str):
        params = {'keys': [key]}
        return self._client.put(
            self._meetings_api_host,
            f'/themes/{theme_id}/finalizeLogos',
            params,
            auth_type=Meetings._auth_type,
        )

    @staticmethod
    def set_start_and_end_params(start_id, end_id):
        params = {}
        if start_id is not None:
            params['start_id'] = start_id
        if end_id is not None:
            params['end_id'] = end_id
        return params
