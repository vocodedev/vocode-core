from warnings import warn

from twilio.rest.trusthub.TrusthubBase import TrusthubBase
from twilio.rest.trusthub.v1.customer_profiles import CustomerProfilesList
from twilio.rest.trusthub.v1.end_user import EndUserList
from twilio.rest.trusthub.v1.end_user_type import EndUserTypeList
from twilio.rest.trusthub.v1.policies import PoliciesList
from twilio.rest.trusthub.v1.supporting_document import SupportingDocumentList
from twilio.rest.trusthub.v1.supporting_document_type import SupportingDocumentTypeList
from twilio.rest.trusthub.v1.trust_products import TrustProductsList


class Trusthub(TrusthubBase):
    @property
    def customer_profiles(self) -> CustomerProfilesList:
        warn(
            "customer_profiles is deprecated. Use v1.customer_profiles instead.",
            DeprecationWarning,
            stacklevel=2,
        )
        return self.v1.customer_profiles

    @property
    def end_users(self) -> EndUserList:
        warn(
            "end_users is deprecated. Use v1.end_users instead.",
            DeprecationWarning,
            stacklevel=2,
        )
        return self.v1.end_users

    @property
    def end_user_types(self) -> EndUserTypeList:
        warn(
            "end_user_types is deprecated. Use v1.end_user_types instead.",
            DeprecationWarning,
            stacklevel=2,
        )
        return self.v1.end_user_types

    @property
    def policies(self) -> PoliciesList:
        warn(
            "policies is deprecated. Use v1.policies instead.",
            DeprecationWarning,
            stacklevel=2,
        )
        return self.v1.policies

    @property
    def supporting_documents(self) -> SupportingDocumentList:
        warn(
            "supporting_documents is deprecated. Use v1.supporting_documents instead.",
            DeprecationWarning,
            stacklevel=2,
        )
        return self.v1.supporting_documents

    @property
    def supporting_document_types(self) -> SupportingDocumentTypeList:
        warn(
            "supporting_document_types is deprecated. Use v1.supporting_document_types instead.",
            DeprecationWarning,
            stacklevel=2,
        )
        return self.v1.supporting_document_types

    @property
    def trust_products(self) -> TrustProductsList:
        warn(
            "trust_products is deprecated. Use v1.trust_products instead.",
            DeprecationWarning,
            stacklevel=2,
        )
        return self.v1.trust_products
