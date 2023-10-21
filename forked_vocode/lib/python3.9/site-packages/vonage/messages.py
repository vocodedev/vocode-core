from ._internal import set_auth_type
from .errors import MessagesError

import re


class Messages:
    valid_message_channels = {'sms', 'mms', 'whatsapp', 'messenger', 'viber_service'}
    valid_message_types = {
        'sms': {'text'},
        'mms': {'image', 'vcard', 'audio', 'video'},
        'whatsapp': {'text', 'image', 'audio', 'video', 'file', 'template', 'sticker', 'custom'},
        'messenger': {'text', 'image', 'audio', 'video', 'file'},
        'viber_service': {'text', 'image', 'video', 'file'},
    }

    def __init__(self, client):
        self._client = client
        self._auth_type = set_auth_type(self._client)

    def send_message(self, params: dict):
        self.validate_send_message_input(params)

        return self._client.post(
            self._client.api_host(),
            "/v1/messages",
            params,
            auth_type=self._auth_type,
        )

    def validate_send_message_input(self, params):
        self._check_input_is_dict(params)
        self._check_valid_message_channel(params)
        self._check_valid_message_type(params)
        self._check_valid_recipient(params)
        self._check_valid_sender(params)
        self._channel_specific_checks(params)
        self._check_valid_client_ref(params)

    def _check_input_is_dict(self, params):
        if type(params) is not dict:
            raise MessagesError(
                'Parameters to the send_message method must be specified as a dictionary.'
            )

    def _check_valid_message_channel(self, params):
        if params['channel'] not in Messages.valid_message_channels:
            raise MessagesError(
                f"""
            "{params['channel']}" is an invalid message channel. 
            Must be one of the following types: {self.valid_message_channels}'
            """
            )

    def _check_valid_message_type(self, params):
        if params['message_type'] not in self.valid_message_types[params['channel']]:
            raise MessagesError(
                f"""
                "{params['message_type']}" is not a valid message type for channel "{params["channel"]}". 
                Must be one of the following types: {self.valid_message_types[params["channel"]]}
            """
            )

    def _check_valid_recipient(self, params):
        if not isinstance(params['to'], str):
            raise MessagesError(f'Message recipient ("to={params["to"]}") not in a valid format.')
        elif params['channel'] != 'messenger' and not re.search(r'^[1-9]\d{6,14}$', params['to']):
            raise MessagesError(
                f'Message recipient number ("to={params["to"]}") not in a valid format.'
            )
        elif params['channel'] == 'messenger' and not 0 < len(params['to']) < 50:
            raise MessagesError(
                f'Message recipient ID ("to={params["to"]}") not in a valid format.'
            )

    def _check_valid_sender(self, params):
        if not isinstance(params['from'], str) or params['from'] == "":
            raise MessagesError(
                f'Message sender ("frm={params["from"]}") set incorrectly. Set a valid name or number for the sender.'
            )

    def _channel_specific_checks(self, params):
        if (
            (
                params['channel'] == 'whatsapp'
                and params['message_type'] == 'template'
                and 'whatsapp' not in params
            )
            or (
                params['channel'] == 'whatsapp'
                and params['message_type'] == 'sticker'
                and 'sticker' not in params
            )
            or (params['channel'] == 'viber_service' and 'viber_service' not in params)
        ):
            raise MessagesError(
                f'''You must specify all required properties for message channel "{params["channel"]}".'''
            )
        elif params['channel'] == 'whatsapp' and params['message_type'] == 'sticker':
            self._check_valid_whatsapp_sticker(params['sticker'])

    def _check_valid_client_ref(self, params):
        if 'client_ref' in params:
            if len(params['client_ref']) <= 100:
                self._client_ref = params['client_ref']
            else:
                raise MessagesError('client_ref can be a maximum of 100 characters.')

    def _check_valid_whatsapp_sticker(self, sticker):
        if ('id' not in sticker and 'url' not in sticker) or ('id' in sticker and 'url' in sticker):
            raise MessagesError(
                'Must specify one, and only one, of "id" or "url" in the "sticker" field.'
            )
