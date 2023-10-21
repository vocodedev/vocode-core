from warnings import warn

from twilio.rest.flex_api.FlexApiBase import FlexApiBase
from twilio.rest.flex_api.v1.assessments import AssessmentsList
from twilio.rest.flex_api.v1.channel import ChannelList
from twilio.rest.flex_api.v1.configuration import ConfigurationList
from twilio.rest.flex_api.v1.flex_flow import FlexFlowList
from twilio.rest.flex_api.v1.insights_assessments_comment import (
    InsightsAssessmentsCommentList,
)
from twilio.rest.flex_api.v1.insights_conversations import InsightsConversationsList
from twilio.rest.flex_api.v1.insights_questionnaires import InsightsQuestionnairesList
from twilio.rest.flex_api.v1.insights_questionnaires_category import (
    InsightsQuestionnairesCategoryList,
)
from twilio.rest.flex_api.v1.insights_questionnaires_question import (
    InsightsQuestionnairesQuestionList,
)
from twilio.rest.flex_api.v1.insights_segments import InsightsSegmentsList
from twilio.rest.flex_api.v1.insights_session import InsightsSessionList
from twilio.rest.flex_api.v1.insights_settings_answer_sets import (
    InsightsSettingsAnswerSetsList,
)
from twilio.rest.flex_api.v1.insights_settings_comment import (
    InsightsSettingsCommentList,
)
from twilio.rest.flex_api.v1.insights_user_roles import InsightsUserRolesList
from twilio.rest.flex_api.v1.interaction import InteractionList
from twilio.rest.flex_api.v1.web_channel import WebChannelList
from twilio.rest.flex_api.v2.web_channels import WebChannelsList


class FlexApi(FlexApiBase):
    @property
    def assessments(self) -> AssessmentsList:
        warn(
            "assessments is deprecated. Use v1.assessments instead.",
            DeprecationWarning,
            stacklevel=2,
        )
        return self.v1.assessments

    @property
    def channel(self) -> ChannelList:
        warn(
            "channel is deprecated. Use v1.channel instead.",
            DeprecationWarning,
            stacklevel=2,
        )
        return self.v1.channel

    @property
    def configuration(self) -> ConfigurationList:
        warn(
            "configuration is deprecated. Use v1.configuration instead.",
            DeprecationWarning,
            stacklevel=2,
        )
        return self.v1.configuration

    @property
    def flex_flow(self) -> FlexFlowList:
        warn(
            "flex_flow is deprecated. Use v1.flex_flow instead.",
            DeprecationWarning,
            stacklevel=2,
        )
        return self.v1.flex_flow

    @property
    def insights_assessments_comment(self) -> InsightsAssessmentsCommentList:
        warn(
            "insights_assessments_comment is deprecated. Use v1.insights_assessments_comment instead.",
            DeprecationWarning,
            stacklevel=2,
        )
        return self.v1.insights_assessments_comment

    @property
    def insights_conversations(self) -> InsightsConversationsList:
        warn(
            "insights_conversations is deprecated. Use v1.insights_conversations instead.",
            DeprecationWarning,
            stacklevel=2,
        )
        return self.v1.insights_conversations

    @property
    def insights_questionnaires(self) -> InsightsQuestionnairesList:
        warn(
            "insights_questionnaires is deprecated. Use v1.insights_questionnaires instead.",
            DeprecationWarning,
            stacklevel=2,
        )
        return self.v1.insights_questionnaires

    @property
    def insights_questionnaires_category(self) -> InsightsQuestionnairesCategoryList:
        warn(
            "insights_questionnaires_category is deprecated. Use v1.insights_questionnaires_category instead.",
            DeprecationWarning,
            stacklevel=2,
        )
        return self.v1.insights_questionnaires_category

    @property
    def insights_questionnaires_question(self) -> InsightsQuestionnairesQuestionList:
        warn(
            "insights_questionnaires_question is deprecated. Use v1.insights_questionnaires_question instead.",
            DeprecationWarning,
            stacklevel=2,
        )
        return self.v1.insights_questionnaires_question

    @property
    def insights_segments(self) -> InsightsSegmentsList:
        warn(
            "insights_segments is deprecated. Use v1.insights_segments instead.",
            DeprecationWarning,
            stacklevel=2,
        )
        return self.v1.insights_segments

    @property
    def insights_session(self) -> InsightsSessionList:
        warn(
            "insights_session is deprecated. Use v1.insights_session instead.",
            DeprecationWarning,
            stacklevel=2,
        )
        return self.v1.insights_session

    @property
    def insights_settings_answer_sets(self) -> InsightsSettingsAnswerSetsList:
        warn(
            "insights_settings_answer_sets is deprecated. Use v1.insights_settings_answer_sets instead.",
            DeprecationWarning,
            stacklevel=2,
        )
        return self.v1.insights_settings_answer_sets

    @property
    def insights_settings_comment(self) -> InsightsSettingsCommentList:
        warn(
            "insights_settings_comment is deprecated. Use v1.insights_settings_comment instead.",
            DeprecationWarning,
            stacklevel=2,
        )
        return self.v1.insights_settings_comment

    @property
    def insights_user_roles(self) -> InsightsUserRolesList:
        warn(
            "insights_user_roles is deprecated. Use v1.insights_user_roles instead.",
            DeprecationWarning,
            stacklevel=2,
        )
        return self.v1.insights_user_roles

    @property
    def interaction(self) -> InteractionList:
        warn(
            "interaction is deprecated. Use v1.interaction instead.",
            DeprecationWarning,
            stacklevel=2,
        )
        return self.v1.interaction

    @property
    def web_channel(self) -> WebChannelList:
        warn(
            "web_channel is deprecated. Use v1.web_channel instead.",
            DeprecationWarning,
            stacklevel=2,
        )
        return self.v1.web_channel

    @property
    def web_channels(self) -> WebChannelsList:
        warn(
            "web_channels is deprecated. Use v2.web_channels instead.",
            DeprecationWarning,
            stacklevel=2,
        )
        return self.v2.web_channels
