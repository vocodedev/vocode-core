from warnings import warn

from twilio.rest.accounts.AccountsBase import AccountsBase
from twilio.rest.accounts.v1.auth_token_promotion import AuthTokenPromotionList
from twilio.rest.accounts.v1.credential import CredentialList
from twilio.rest.accounts.v1.secondary_auth_token import SecondaryAuthTokenList


class Accounts(AccountsBase):
    @property
    def auth_token_promotion(self) -> AuthTokenPromotionList:
        warn(
            "auth_token_promotion is deprecated. Use v1.auth_token_promotion instead.",
            DeprecationWarning,
            stacklevel=2,
        )
        return self.v1.auth_token_promotion

    @property
    def credentials(self) -> CredentialList:
        warn(
            "credentials is deprecated. Use v1.credentials instead.",
            DeprecationWarning,
            stacklevel=2,
        )
        return self.v1.credentials

    @property
    def secondary_auth_token(self) -> SecondaryAuthTokenList:
        warn(
            "secondary_auth_token is deprecated. Use v1.secondary_auth_token instead.",
            DeprecationWarning,
            stacklevel=2,
        )
        return self.v1.secondary_auth_token
