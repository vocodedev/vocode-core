import jwt as jwt_lib
import time


__all__ = ["Jwt", "JwtDecodeError"]


class JwtDecodeError(Exception):
    pass


class Jwt(object):
    """Base class for building a Json Web Token"""

    GENERATE = object()
    ALGORITHM = "HS256"

    def __init__(
        self,
        secret_key,
        issuer,
        subject=None,
        algorithm=None,
        nbf=GENERATE,
        ttl=3600,
        valid_until=None,
    ):
        self.secret_key = secret_key
        """:type str: The secret used to encode the JWT"""
        self.issuer = issuer
        """:type str: The issuer of this JWT"""
        self.subject = subject
        """:type str: The subject of this JWT, omitted from payload by default"""
        self.algorithm = algorithm or self.ALGORITHM
        """:type str: The algorithm used to encode the JWT, defaults to 'HS256'"""
        self.nbf = nbf
        """:type int: Time in secs since epoch before which this JWT is invalid. Defaults to now."""
        self.ttl = ttl
        """:type int: Time to live of the JWT in seconds, defaults to 1 hour"""
        self.valid_until = valid_until
        """:type int: Time in secs since epoch this JWT is valid for. Overrides ttl if provided."""

        self.__decoded_payload = None
        self.__decoded_headers = None

    def _generate_payload(self):
        """:rtype: dict the payload of the JWT to send"""
        raise NotImplementedError("Subclass must provide a payload.")

    def _generate_headers(self):
        """:rtype dict: Additional headers to include in the JWT, defaults to an empty dict"""
        return {}

    @classmethod
    def _from_jwt(cls, headers, payload, key=None):
        """
        Class specific implementation of from_jwt which should take jwt components and return
        and instance of this Class with jwt information loaded.
        :return: Jwt object containing the headers, payload and key
        """
        jwt = Jwt(
            secret_key=key,
            issuer=payload.get("iss", None),
            subject=payload.get("sub", None),
            algorithm=headers.get("alg", None),
            valid_until=payload.get("exp", None),
            nbf=payload.get("nbf", None),
        )
        jwt.__decoded_payload = payload
        jwt.__decoded_headers = headers
        return jwt

    @property
    def payload(self):
        if self.__decoded_payload:
            return self.__decoded_payload

        payload = self._generate_payload().copy()
        payload["iss"] = self.issuer
        payload["exp"] = int(time.time()) + self.ttl
        if self.nbf is not None:
            if self.nbf == self.GENERATE:
                payload["nbf"] = int(time.time())
            else:
                payload["nbf"] = self.nbf
        if self.valid_until:
            payload["exp"] = self.valid_until
        if self.subject:
            payload["sub"] = self.subject

        return payload

    @property
    def headers(self):
        if self.__decoded_headers:
            return self.__decoded_headers

        headers = self._generate_headers().copy()
        headers["typ"] = "JWT"
        headers["alg"] = self.algorithm
        return headers

    def to_jwt(self, ttl=None):
        """
        Encode this JWT object into a JWT string
        :param int ttl: override the ttl configured in the constructor
        :rtype: str The JWT string
        """

        if not self.secret_key:
            raise ValueError("JWT does not have a signing key configured.")

        headers = self.headers.copy()

        payload = self.payload.copy()
        if ttl:
            payload["exp"] = int(time.time()) + ttl

        return jwt_lib.encode(
            payload, self.secret_key, algorithm=self.algorithm, headers=headers
        )

    @classmethod
    def from_jwt(cls, jwt, key=""):
        """
        Decode a JWT string into a Jwt object
        :param str jwt: JWT string
        :param Optional[str] key: key used to verify JWT signature, if not provided then validation
                                  is skipped.
        :raises JwtDecodeError if decoding JWT fails for any reason.
        :return: A DecodedJwt object containing the jwt information.
        """
        verify = True if key else False

        try:
            headers = jwt_lib.get_unverified_header(jwt)

            alg = headers.get("alg")
            if alg != cls.ALGORITHM:
                raise ValueError(
                    f"Incorrect decoding algorithm {alg}, "
                    f"expecting {cls.ALGORITHM}."
                )

            payload = jwt_lib.decode(
                jwt,
                key,
                algorithms=[cls.ALGORITHM],
                options={
                    "verify_signature": verify,
                    "verify_exp": True,
                    "verify_nbf": True,
                },
            )
        except Exception as e:
            raise JwtDecodeError(getattr(e, "message", str(e)))

        return cls._from_jwt(headers, payload, key)

    def __str__(self):
        return "<JWT {}>".format(self.to_jwt())
