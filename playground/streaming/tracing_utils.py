from collections import defaultdict
from opentelemetry.sdk.trace.export import SpanExporter

class PrintDurationSpanExporter(SpanExporter):
    def __init__(self):
        super().__init__()
        self.spans = defaultdict(list)

    def export(self, spans):
        for span in spans:
            duration_ns = span.end_time - span.start_time
            duration_s = duration_ns / 1e9
            self.spans[span.name].append(duration_s)

    def shutdown(self):
        for name, durations in self.spans.items():
            print(f"{name}: {sum(durations) / len(durations)}")
