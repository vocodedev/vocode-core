raise DeprecationWarning(
    "OpenTelemetry support is currently deprecated, but planned to be re-enabled in the future."
)

import argparse
import re
from collections import defaultdict
from threading import RLock
from typing import Any, Dict, List, Optional, Union

from opentelemetry.sdk.metrics.export import (
    HistogramDataPoint,
    Metric,
    MetricReader,
    MetricsData,
    NumberDataPoint,
)
from opentelemetry.sdk.trace.export import SpanExporter

NANOSECONDS_PER_SECOND = 1e9


class PrintDurationSpanExporter(SpanExporter):
    def __init__(self):
        super().__init__()
        self.spans = defaultdict(list)

    def export(self, spans):
        for span in spans:
            duration_ns = span.end_time - span.start_time
            duration_s = duration_ns / NANOSECONDS_PER_SECOND
            self.spans[span.name].append(duration_s)

    def shutdown(self):
        for name, durations in self.spans.items():
            print(f"{name}: {sum(durations) / len(durations)}")


def get_final_metrics(scope_metrics, final_spans=None):
    if len(scope_metrics) > 0:
        metric_results: List[Metric] = scope_metrics[0].metrics
        formatted_metric_results: Dict[str, Any] = {
            metric.name: metric.data.data_points[0] for metric in metric_results
        }
        final_metrics = {}
        for metric_name, raw_metric in formatted_metric_results.items():
            if re.match(r"transcriber.*\.min_latency", metric_name):
                final_metrics[metric_name] = raw_metric.min
            elif re.match(r"transcriber.*\.max_latency", metric_name):
                final_metrics[metric_name] = raw_metric.max
            elif re.match(r"transcriber.*\.avg_latency", metric_name):
                transcriber_str = metric_name.split(".")[1]
                final_metrics[metric_name] = (
                    raw_metric.sum
                    / formatted_metric_results[f"transcriber.{transcriber_str}.duration"].sum
                )
            elif re.match(r"agent.*\.total_characters", metric_name) and final_spans:
                agent_str = metric_name.split(".", 1)[1].rsplit(".", 1)[0]
                generate_total_key = f"agent.{agent_str}.generate_total"
                respond_total_key = f"agent.{agent_str}.respond_total"
                final_metrics[f"agent.{agent_str}.characters_per_second"] = raw_metric.value / (
                    sum(final_spans[generate_total_key])
                    if generate_total_key in final_spans
                    else sum(final_spans[respond_total_key])
                )
            else:
                try:
                    final_metrics[metric_name] = raw_metric.value
                except AttributeError:
                    pass
        return final_metrics


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
        final_metrics = get_final_metrics(scope_metrics, final_spans=None)
        for key, value in final_metrics.items():
            print(f"{key}: {value}")


def make_parser_and_maybe_trace():
    parser = argparse.ArgumentParser()
    parser.add_argument("--trace", action="store_true", help="Log latencies and other statistics")
    args = parser.parse_args()
    if args.trace:
        from opentelemetry import trace
        from opentelemetry.sdk.resources import Resource
        from opentelemetry.sdk.trace import TracerProvider
        from opentelemetry.sdk.trace.export import SimpleSpanProcessor

        trace.set_tracer_provider(TracerProvider(resource=Resource.create({})))
        span_exporter = PrintDurationSpanExporter()
        trace.get_tracer_provider().add_span_processor(  # type: ignore
            SimpleSpanProcessor(span_exporter)
        )
