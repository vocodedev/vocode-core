import logging
from enum import Enum
import time
from typing import List, Dict

class LatencyType(Enum):
    TRANSCRIPTION = "transcription"
    AGENT = "agent"
    SYNTHESIS = "synthesis"
    STREAMING = "streaming"

DEFAULT_ROUNDING_DIGITS = 4

class LatencyManager:
    def __init__(self, rounding_digits: int = DEFAULT_ROUNDING_DIGITS):
        self.latencies: Dict[LatencyType, List[float]] = {
            latency_type: [] for latency_type in LatencyType
        }
        self.averages: Dict[LatencyType, float] = {}
        self.rounding_digits = rounding_digits
    
    def measure_latency(self, latency_type, func, *args, **kwargs):
        start_time = time.time()
        result = func(*args, **kwargs)
        latency = time.time() - start_time
        self.add_latency(latency_type, latency)
        return result

    def add_latency(self, latency_type, latency):
        latency = self.round_latency(latency)
        self.latencies[latency_type].append(latency)

    def get_latency(self, latency_type):
        return self.latencies[latency_type][-1]

    def calculate_average_latency(self, latency_type):
        latencies = self.latencies[latency_type]
        if not latencies:
            return 0.0
        return self.round_latency(sum(latencies) / len(latencies))

    def calculate_average_latencies(self):
        averages = {}
        for latency_type in self.latencies:
            if latency_type == LatencyType.STREAMING:
                continue
            average_latency = self.calculate_average_latency(latency_type)
            averages[latency_type] = average_latency
        self.averages = averages
        return averages
    
    def calculate_total_average_latencies(self):
        if not self.averages:
            self.calculate_average_latencies()
        return self.round_latency(sum(self.averages.values()) / len(self.averages))
    
    def round_latency(self, latency):
        return round(latency, self.rounding_digits)

    def log_turn_based_latencies(self, logger):
        logger.info(f"Latency - Transcription: {self.get_latency(LatencyType.TRANSCRIPTION)} seconds, Agent: {self.get_latency(LatencyType.AGENT)} seconds, Synthesis: {self.get_latency(LatencyType.SYNTHESIS)} seconds")
    
    def log_average_turn_based_latencies(self, logger):
        average_latencies = self.calculate_average_latencies()
        logger.info("\nAverage latencies:")
        for latency_type in average_latencies:
            logger.info(f"Average {latency_type.value} latency: {average_latencies[latency_type]} seconds")
        logger.info(f"Total average latency: {self.calculate_total_average_latencies()} seconds")
    
    def log_streaming_latency(self, logger):
        logger.info(f"Streaming Latency: {self.get_latency(LatencyType.STREAMING)} seconds")
    
    def log_average_streaming_latency(self, logger):
        logger.info(f"Average Streaming Latency: {self.calculate_average_latency(LatencyType.STREAMING)} seconds")
        
        