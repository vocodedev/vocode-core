from __future__ import annotations
from typing import TYPE_CHECKING, Optional, Union

from .errors import SubaccountsError

if TYPE_CHECKING:
    from vonage import Client


class Subaccounts:
    """Class containing methods for working with the Vonage Subaccounts API."""

    default_start_date = '1970-01-01T00:00:00Z'

    def __init__(self, client: Client):
        self._client = client
        self._api_key = self._client.api_key
        self._api_host = self._client.api_host()
        self._auth_type = 'header'

    def list_subaccounts(self):
        return self._client.get(
            self._api_host,
            f'/accounts/{self._api_key}/subaccounts',
            auth_type=self._auth_type,
        )

    def create_subaccount(
        self,
        name: str,
        secret: Optional[str] = None,
        use_primary_account_balance: Optional[bool] = None,
    ):
        params = {'name': name, 'secret': secret}
        if self._is_boolean(use_primary_account_balance):
            params['use_primary_account_balance'] = use_primary_account_balance

        return self._client.post(
            self._api_host,
            f'/accounts/{self._api_key}/subaccounts',
            params=params,
            auth_type=self._auth_type,
        )

    def get_subaccount(self, subaccount_key: str):
        return self._client.get(
            self._api_host,
            f'/accounts/{self._api_key}/subaccounts/{subaccount_key}',
            auth_type=self._auth_type,
        )

    def modify_subaccount(
        self,
        subaccount_key: str,
        suspended: Optional[bool] = None,
        use_primary_account_balance: Optional[bool] = None,
        name: Optional[str] = None,
    ):
        params = {'name': name}
        if self._is_boolean(suspended):
            params['suspended'] = suspended
        if self._is_boolean(use_primary_account_balance):
            params['use_primary_account_balance'] = use_primary_account_balance

        return self._client.patch(
            self._api_host,
            f'/accounts/{self._api_key}/subaccounts/{subaccount_key}',
            params=params,
            auth_type=self._auth_type,
        )

    def list_credit_transfers(
        self,
        start_date: str = default_start_date,
        end_date: Optional[str] = None,
        subaccount: Optional[str] = None,
    ):
        params = {
            'start_date': start_date,
            'end_date': end_date,
            'subaccount': subaccount,
        }

        return self._client.get(
            self._api_host,
            f'/accounts/{self._api_key}/credit-transfers',
            params=params,
            auth_type=self._auth_type,
        )

    def transfer_credit(
        self,
        from_: str,
        to: str,
        amount: Union[float, int],
        reference: str = None,
    ):
        params = {
            'from': from_,
            'to': to,
            'amount': amount,
            'reference': reference,
        }

        return self._client.post(
            self._api_host,
            f'/accounts/{self._api_key}/credit-transfers',
            params=params,
            auth_type=self._auth_type,
        )

    def list_balance_transfers(
        self,
        start_date: str = default_start_date,
        end_date: Optional[str] = None,
        subaccount: Optional[str] = None,
    ):
        params = {
            'start_date': start_date,
            'end_date': end_date,
            'subaccount': subaccount,
        }

        return self._client.get(
            self._api_host,
            f'/accounts/{self._api_key}/balance-transfers',
            params=params,
            auth_type=self._auth_type,
        )

    def transfer_balance(
        self,
        from_: str,
        to: str,
        amount: Union[float, int],
        reference: str = None,
    ):
        params = {'from': from_, 'to': to, 'amount': amount, 'reference': reference}

        return self._client.post(
            self._api_host,
            f'/accounts/{self._api_key}/balance-transfers',
            params=params,
            auth_type=self._auth_type,
        )

    def transfer_number(self, from_: str, to: str, number: int, country: str):
        params = {'from': from_, 'to': to, 'number': number, 'country': country}
        return self._client.post(
            self._api_host,
            f'/accounts/{self._api_key}/transfer-number',
            params=params,
            auth_type=self._auth_type,
        )

    def _is_boolean(self, var):
        if var is not None:
            if type(var) == bool:
                return True
            else:
                raise SubaccountsError(
                    f'If providing a value, it needs to be a boolean. You provided: "{var}"'
                )
