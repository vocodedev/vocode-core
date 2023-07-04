from vocode.streaming.output_device.base_output_device import BaseOutputDevice


class SilentOutputDevice(BaseOutputDevice):
    def consume_nonblocking(self, chunk: bytes):
        pass
