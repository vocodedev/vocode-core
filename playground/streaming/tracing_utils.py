import re
from collections import defaultdict
from threading import RLock
from typing import Optional
from opentelemetry.sdk.trace.export import SpanExporter
from opentelemetry.sdk.metrics.export import MetricReader
from opentelemetry.sdk.metrics.export import MetricsData


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


class SpecificStatisticsReader(MetricReader):
    """Implementation of `MetricReader` that returns its metrics from :func:`get_metrics_data`.

    This is useful for e.g. unit tests.
    """

    def __init__(self) -> None:
        super().__init__()
        self._lock = RLock()
        self._metrics_data: Optional[MetricsData] = None

    def get_metrics_data(self):
        """Reads and returns current metrics from the SDK"""
        with self._lock:
            self.collect()
            metrics_data = self._metrics_data
            self._metrics_data = None
        return metrics_data

    def _receive_metrics(
        self,
        metrics_data: MetricsData,
        timeout_millis: float = 10_000,
        **kwargs,
    ) -> None:
        with self._lock:
            self._metrics_data = metrics_data

    def shutdown(self, timeout_millis: float = 30_000, **kwargs) -> None:
        scope_metrics = self.get_metrics_data().resource_metrics[0].scope_metrics
        if len(scope_metrics) > 0:
            metric_results = scope_metrics[0].metrics
            metric_results = {
                metric.name: metric.data.data_points[0] for metric in metric_results
            }
            final_metrics = {}
            for metric_name, raw_metric in metric_results.items():
                if re.match(r"transcriber.*\.min_latency", metric_name):
                    final_metrics[metric_name] = raw_metric.min
                elif re.match(r"transcriber.*\.max_latency", metric_name):
                    final_metrics[metric_name] = raw_metric.max
                elif re.match(r"transcriber.*\.avg_latency", metric_name):
                    transcriber_str = metric_name.split(".")[1]
                    final_metrics[metric_name] = (
                        raw_metric.sum
                        / metric_results[f"transcriber.{transcriber_str}.duration"].sum
                    )
                else:
                    final_metrics[metric_name] = raw_metric.value
            for key, value in final_metrics.items():
                print(f"{key}: {value}")
