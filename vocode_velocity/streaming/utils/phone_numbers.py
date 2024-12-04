import phonenumbers
from phonenumbers import PhoneNumberFormat

NUMBER_PARSE_ERROR = "Input number cannot be interpreted as a phone number. If passing an international number, please include the country code (e.g. +49 for German numbers)"


def parse_number_e164(phone_number: str) -> phonenumbers.PhoneNumber:
    if not phone_number.startswith("+"):
        phone_number = "+" + phone_number
    return phonenumbers.parse(phone_number, None)


def parse_number_usa_fallback_to_e164(phone_number: str) -> phonenumbers.PhoneNumber:
    try:
        phone_number_obj = phonenumbers.parse(phone_number, "US")
        valid = phonenumbers.is_valid_number(phone_number_obj)
        return phone_number_obj if valid else parse_number_e164(phone_number)
    except phonenumbers.phonenumberutil.NumberParseException:
        return parse_number_e164(phone_number)


def parse_phone_number(phone_number: str) -> phonenumbers.PhoneNumber:
    if phone_number.startswith("+"):
        # If we have a plus we know its e164
        return parse_number_e164(phone_number)
    else:
        # If we don't have a plus, we try as USA with e164 fallback
        return parse_number_usa_fallback_to_e164(phone_number)


def sanitize_phone_number(phone_number: str) -> str:
    phone_number_obj: phonenumbers.PhoneNumber

    try:
        phone_number_obj = parse_phone_number(phone_number)
    except Exception:
        raise ValueError(NUMBER_PARSE_ERROR)

    if not phonenumbers.is_valid_number(phone_number_obj):
        raise ValueError(NUMBER_PARSE_ERROR)

    return phonenumbers.format_number(phone_number_obj, PhoneNumberFormat.E164).replace("+", "")
