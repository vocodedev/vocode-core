from warnings import warn

from twilio.rest.bulkexports.BulkexportsBase import BulkexportsBase
from twilio.rest.bulkexports.v1.export import ExportList
from twilio.rest.bulkexports.v1.export_configuration import ExportConfigurationList


class Bulkexports(BulkexportsBase):
    @property
    def exports(self) -> ExportList:
        warn(
            "exports is deprecated. Use v1.exports instead.",
            DeprecationWarning,
            stacklevel=2,
        )
        return self.v1.exports

    @property
    def export_configuration(self) -> ExportConfigurationList:
        warn(
            "export_configuration is deprecated. Use v1.export_configuration instead.",
            DeprecationWarning,
            stacklevel=2,
        )
        return self.v1.export_configuration
