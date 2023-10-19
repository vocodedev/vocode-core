from hashlib import sha256

from twilio.jwt import Jwt


class ClientValidationJwt(Jwt):
    """A JWT included on requests so that Twilio can verify request authenticity"""

    __CTY = "twilio-pkrv;v=1"
    ALGORITHM = "RS256"

    def __init__(
        self, account_sid, api_key_sid, credential_sid, private_key, validation_payload
    ):
        """
        Create a new ClientValidationJwt
        :param str account_sid: A Twilio Account Sid starting with 'AC'
        :param str api_key_sid: A Twilio API Key Sid starting with 'SK'
        :param str credential_sid: A Credential Sid starting with 'CR',
                                   public key Twilio will use to verify the JWT.
        :param str private_key: The private key used to sign the JWT.
        :param ValidationPayload validation_payload: information from the request to sign
        """
        super(ClientValidationJwt, self).__init__(
            secret_key=private_key,
            issuer=api_key_sid,
            subject=account_sid,
            algorithm=self.ALGORITHM,
            ttl=300,  # 5 minute ttl
        )
        self.credential_sid = credential_sid
        self.validation_payload = validation_payload

    def _generate_headers(self):
        return {"cty": ClientValidationJwt.__CTY, "kid": self.credential_sid}

    def _generate_payload(self):
        # Lowercase header keys, combine and sort headers with list values
        all_headers = {
            k.lower(): self._sort_and_join(v, ",")
            for k, v in self.validation_payload.all_headers.items()
        }
        # Names of headers we are signing in the jwt
        signed_headers = sorted(self.validation_payload.signed_headers)

        # Stringify headers, only include headers in signed_headers
        headers_str = [
            "{}:{}".format(h, all_headers[h])
            for h in signed_headers
            if h in all_headers
        ]
        headers_str = "\n".join(headers_str)

        # Sort query string parameters
        query_string = self.validation_payload.query_string.split("&")
        query_string = self._sort_and_join(query_string, "&")

        req_body_hash = self._hash(self.validation_payload.body) or ""

        signed_headers_str = ";".join(signed_headers)

        signed_payload = [
            self.validation_payload.method,
            self.validation_payload.path,
            query_string,
        ]

        if headers_str:
            signed_payload.append(headers_str)
        signed_payload.append("")
        signed_payload.append(signed_headers_str)
        signed_payload.append(req_body_hash)

        signed_payload = "\n".join(signed_payload)

        return {"hrh": signed_headers_str, "rqh": self._hash(signed_payload)}

    @classmethod
    def _sort_and_join(cls, values, joiner):
        if isinstance(values, str):
            return values
        return joiner.join(sorted(values))

    @classmethod
    def _hash(cls, input_str):
        if not input_str:
            return input_str

        if not isinstance(input_str, bytes):
            input_str = input_str.encode("utf-8")

        return sha256(input_str).hexdigest()
