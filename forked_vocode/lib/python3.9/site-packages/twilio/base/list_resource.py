from twilio.base.version import Version


class ListResource(object):
    def __init__(self, version: Version):
        self._version = version
