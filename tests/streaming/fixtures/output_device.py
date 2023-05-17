from vocode.streaming.output_device.base_output_device import BaseOutputDevice


class SilentOutputDevice(BaseOutputDevice):
    def send_nonblocking(self, chunk: bytes):
        pass
