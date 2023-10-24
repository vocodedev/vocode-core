import re
from typing import List, Set, Optional

from pydantic import BaseModel


class ValidationResult(BaseModel):
    text: str
    reason: Optional[str] = None

    @property
    def valid(self):
        return self.reason is None


class ResponseCheck:
    def validate(self, response: str) -> ValidationResult:
        raise NotImplementedError("This method should be implemented in a subclass")


class SpecialCharacterCheck(ResponseCheck):
    def validate(self, response: str) -> ValidationResult:
        reason = "Special characters check failed" if bool(re.search(r'[{}\[\]_()]', response)) else None
        return ValidationResult(text=response, reason=reason)


class LengthCheck(ResponseCheck):
    def __init__(self, max_length: int):
        self.max_length = max_length

    def validate(self, response: str) -> ValidationResult:
        reason = f"Length check failed: {len(response)} exceeds limit of {self.max_length}" if len(
            response) > self.max_length else None
        return ValidationResult(text=response, reason=reason)


class ProhibitedPhraseCheck(ResponseCheck):
    def __init__(self, prohibited_phrases: Set[str]):
        self.prohibited_phrases = prohibited_phrases

    def _normalize(self, text: str) -> str:
        """Normalize text for prohibited phrase check."""
        return text.lower().strip()

    def validate(self, response: str) -> ValidationResult:
        for phrase in self.prohibited_phrases:
            if self._normalize(phrase) in self._normalize(response):
                return ValidationResult(text=response,
                                        reason=f"Prohibited phrase check failed: contains '{phrase}'")
        return ValidationResult(text=response, reason=None)


class ResponseValidator:
    def __init__(self, checks: List[ResponseCheck]):
        self.checks = checks

    def validate(self, response: str) -> ValidationResult:
        for check in self.checks:
            validation_result = check.validate(response)
            if not validation_result.valid:
                return validation_result
        return ValidationResult(text=response, reason=None)


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
