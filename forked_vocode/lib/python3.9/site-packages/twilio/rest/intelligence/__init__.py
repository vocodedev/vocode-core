from twilio.rest.intelligence.IntelligenceBase import IntelligenceBase
from twilio.rest.intelligence.v2.service import ServiceList
from twilio.rest.intelligence.v2.transcript import TranscriptList


class Intelligence(IntelligenceBase):
    @property
    def transcripts(self) -> TranscriptList:
        return self.v2.transcripts

    @property
    def services(self) -> ServiceList:
        return self.v2.services
