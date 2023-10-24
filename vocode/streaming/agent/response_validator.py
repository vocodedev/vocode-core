import re
from typing import List, Set, Optional, Tuple


class ResponseCheck:
    def validate(self, response: str) -> Tuple[bool, Optional[str]]:
        raise NotImplementedError("This method should be implemented in a subclass")


class SpecialCharacterCheck(ResponseCheck):
    def validate(self, response: str) -> Tuple[bool, Optional[str]]:
        if bool(re.search(r'[{}\[\]_()]', response)):
            return False, "Special characters check failed"
        return True, None


class LengthCheck(ResponseCheck):
    def __init__(self, max_length: int):
        self.max_length = max_length

    def validate(self, response: str) -> Tuple[bool, Optional[str]]:
        if len(response) > self.max_length:
            return False, f"Length check failed: {len(response)} exceeds limit of {self.max_length}"
        return True, None


class ProhibitedPhraseCheck(ResponseCheck):
    def __init__(self, prohibited_phrases: Set[str]):
        self.prohibited_phrases = prohibited_phrases

    def _normalize(self, text: str) -> str:
        """Normalize text for prohibited phrase check."""
        return text.lower().strip()

    def validate(self, response: str) -> Tuple[bool, Optional[str]]:
        for phrase in self.prohibited_phrases:
            if self._normalize(phrase) in self._normalize(response):
                return False, f"Prohibited phrase check failed: contains '{phrase}'"
        return True, None


class ResponseValidator:
    def __init__(self, checks: List[ResponseCheck]):
        self.checks = checks

    def validate(self, response: str) -> Tuple[bool, Optional[str]]:
        for check in self.checks:
            success, error_message = check.validate(response)
            if not success:
                return False, error_message
        return True, None


class DefaultResponseValidator(ResponseValidator):
    """
    Basic validator that checks for special characters, length, and prohibited phrases.
    """

    def __init__(self, max_length: int = 280, prohibited_phrases: Optional[Set[str]] = None):
        checks = [
            SpecialCharacterCheck(),
            LengthCheck(max_length),
            ProhibitedPhraseCheck(prohibited_phrases or set())
        ]
        super().__init__(checks)



if __name__ == "__main__":
    # simple showcase instead of unittests (for now
    validator = DefaultResponseValidator()
    print(validator.validate("Hello"))
    print(validator.validate("Hello ["))
    print(validator.validate("Hello" * 100))
