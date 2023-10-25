from __future__ import annotations
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from vonage import Client

from .errors import UsersError
from ._internal import set_auth_type


class Users:
    """Class containing methods for user management as part of the Application API."""

    def __init__(self, client: Client):
        self._client = client
        self._auth_type = set_auth_type(self._client)

    def list_users(
        self,
        page_size: int = None,
        order: str = 'asc',
        cursor: str = None,
        name: str = None,
    ):
        """
        Lists the name and user id of all users associated with the account.
        For complete information on a user, call Users.get_user, passing in the user id.
        """

        if order.lower() not in ('asc', 'desc'):
            raise UsersError(
                'Invalid order parameter. Must be one of: "asc", "desc", "ASC", "DESC".'
            )

        params = {'page_size': page_size, 'order': order.lower(), 'cursor': cursor, 'name': name}
        return self._client.get(
            self._client.api_host(),
            '/v1/users',
            params,
            auth_type=self._auth_type,
        )

    def create_user(self, params: dict = None):
        self._client.headers['Content-Type'] = 'application/json'
        return self._client.post(
            self._client.api_host(),
            '/v1/users',
            params,
            auth_type=self._auth_type,
        )

    def get_user(self, user_id: str):
        return self._client.get(
            self._client.api_host(),
            f'/v1/users/{user_id}',
            auth_type=self._auth_type,
        )

    def update_user(self, user_id: str, params: dict):
        return self._client.patch(
            self._client.api_host(),
            f'/v1/users/{user_id}',
            params,
            auth_type=self._auth_type,
        )

    def delete_user(self, user_id: str):
        return self._client.delete(
            self._client.api_host(),
            f'/v1/users/{user_id}',
            auth_type=self._auth_type,
        )
