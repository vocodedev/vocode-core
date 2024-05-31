import re

import pytest

from vocode.streaming.utils.phone_numbers import NUMBER_PARSE_ERROR, sanitize_phone_number


def test_sanitize_phone_number_valid_number_without_region():
    phone = "14155552671"  # This is a valid US number
    expected_result = "14155552671"
    result = sanitize_phone_number(phone)
    assert result == expected_result


def test_sanitize_phone_number_valid_number_with_plus():
    phone = "+14155552671"
    expected_result = "14155552671"
    result = sanitize_phone_number(phone)
    assert result == expected_result


def test_sanitize_phone_number_invalid_number_without_region():
    phone = "gibberish"
    with pytest.raises(ValueError, match=re.escape(NUMBER_PARSE_ERROR)):
        sanitize_phone_number(phone)


def test_sanitize_phone_number_invalid_number_with_region():
    phone = "+1911"
    with pytest.raises(ValueError, match=re.escape(NUMBER_PARSE_ERROR)):
        sanitize_phone_number(phone)


def test_sanitize_phone_number_valid_number_with_non_us_region():
    phone = "+443031237301"  # This is a valid GB number for Buckingham Palace
    expected_result = "443031237301"
    result = sanitize_phone_number(phone)
    assert result == expected_result

    # test same number with no +
    result = sanitize_phone_number(phone[1:])
    assert result == expected_result


def test_sanitize_phone_number_adds_country_code():
    phone = "4155552222"
    expected_result = "14155552222"
    result = sanitize_phone_number(phone)
    assert result == expected_result
