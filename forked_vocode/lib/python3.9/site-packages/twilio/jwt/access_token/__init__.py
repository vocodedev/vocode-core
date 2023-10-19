import time

from twilio.jwt import Jwt


class AccessTokenGrant(object):
    """A Grant giving access to a Twilio Resource"""

    @property
    def key(self):
        """:rtype str Grant's twilio specific key"""
        raise NotImplementedError("Grant must have a key property.")

    def to_payload(self):
        """:return: dict something"""
        raise NotImplementedError("Grant must implement to_payload.")

    def __str__(self):
        return "<{} {}>".format(self.__class__.__name__, self.to_payload())


class AccessToken(Jwt):
    """Access Token containing one or more AccessTokenGrants used to access Twilio Resources"""

    ALGORITHM = "HS256"

    def __init__(
        self,
        account_sid,
        signing_key_sid,
        secret,
        grants=None,
        identity=None,
        nbf=Jwt.GENERATE,
        ttl=3600,
        valid_until=None,
        region=None,
    ):
        grants = grants or []
        if any(not isinstance(g, AccessTokenGrant) for g in grants):
            raise ValueError("Grants must be instances of AccessTokenGrant.")

        self.account_sid = account_sid
        self.signing_key_sid = signing_key_sid
        self.identity = identity
        self.region = region
        self.grants = grants
        super(AccessToken, self).__init__(
            secret_key=secret,
            algorithm=self.ALGORITHM,
            issuer=signing_key_sid,
            subject=self.account_sid,
            nbf=nbf,
            ttl=ttl,
            valid_until=valid_until,
        )

    def add_grant(self, grant):
        """Add a grant to this AccessToken"""
        if not isinstance(grant, AccessTokenGrant):
            raise ValueError("Grant must be an instance of AccessTokenGrant.")
        self.grants.append(grant)

    def _generate_headers(self):
        headers = {"cty": "twilio-fpa;v=1"}
        if self.region and isinstance(self.region, str):
            headers["twr"] = self.region
        return headers

    def _generate_payload(self):
        now = int(time.time())
        payload = {
            "jti": "{}-{}".format(self.signing_key_sid, now),
            "grants": {grant.key: grant.to_payload() for grant in self.grants},
        }
        if self.identity:
            payload["grants"]["identity"] = self.identity
        return payload

    def __str__(self):
        return "<{} {}>".format(self.__class__.__name__, self.to_jwt())
