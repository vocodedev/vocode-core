from twilio.base.version import Version


class InstanceResource(object):
    def __init__(self, version: Version):
        self._version = version
