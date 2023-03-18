from twilio.jwt.access_token import AccessToken

from vocode.models.telephony import InternalTwilioConfig


def create_access_token(twilio_config: InternalTwilioConfig):
    return AccessToken(
        twilio_config.account_sid,
        twilio_config.api_key,
        twilio_config.api_secret,
        identity="user",
    )
