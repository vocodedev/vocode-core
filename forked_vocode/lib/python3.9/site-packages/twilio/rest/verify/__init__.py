from warnings import warn

from twilio.rest.verify.VerifyBase import VerifyBase
from twilio.rest.verify.v2.form import FormList
from twilio.rest.verify.v2.safelist import SafelistList
from twilio.rest.verify.v2.service import ServiceList
from twilio.rest.verify.v2.template import TemplateList
from twilio.rest.verify.v2.verification_attempt import VerificationAttemptList
from twilio.rest.verify.v2.verification_attempts_summary import (
    VerificationAttemptsSummaryList,
)


class Verify(VerifyBase):
    @property
    def forms(self) -> FormList:
        warn(
            "forms is deprecated. Use v2.forms instead.",
            DeprecationWarning,
            stacklevel=2,
        )
        return self.v2.forms

    @property
    def safelist(self) -> SafelistList:
        warn(
            "safelist is deprecated. Use v2.safelist instead.",
            DeprecationWarning,
            stacklevel=2,
        )
        return self.v2.safelist

    @property
    def services(self) -> ServiceList:
        warn(
            "services is deprecated. Use v2.services instead.",
            DeprecationWarning,
            stacklevel=2,
        )
        return self.v2.services

    @property
    def verification_attempts(self) -> VerificationAttemptList:
        warn(
            "verification_attempts is deprecated. Use v2.verification_attempts instead.",
            DeprecationWarning,
            stacklevel=2,
        )
        return self.v2.verification_attempts

    @property
    def verification_attempts_summary(self) -> VerificationAttemptsSummaryList:
        warn(
            "verification_attempts_summary is deprecated. Use v2.verification_attempts_summary instead.",
            DeprecationWarning,
            stacklevel=2,
        )
        return self.v2.verification_attempts_summary

    @property
    def templates(self) -> TemplateList:
        warn(
            "templates is deprecated. Use v2.templates instead.",
            DeprecationWarning,
            stacklevel=2,
        )
        return self.v2.templates
