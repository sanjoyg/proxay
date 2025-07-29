import asyncio
import threading
from termcolor import cprint

class MimicStatsCollector:
    def __init__(self, verbose: bool = False):
        self.total_requests = 0
        self.cache_hits = 0
        self.cache_misses = 0
        self.verbose = verbose
        self._lock = threading.Lock()
        self._requests_since_last_report = 0

    def record_hit(self):
        with self._lock:
            self.total_requests += 1
            self.cache_hits += 1
            self._requests_since_last_report += 1

    def record_miss(self):
        with self._lock:
            self.total_requests += 1
            self.cache_misses += 1
            self._requests_since_last_report += 1

    def report(self):
        if not self.verbose:
            return

        with self._lock:
            if self._requests_since_last_report == 0:
                return

            hit_percentage = (self.cache_hits / self.total_requests) * 100 if self.total_requests > 0 else 0
            miss_percentage = (self.cache_misses / self.total_requests) * 100 if self.total_requests > 0 else 0

            cprint("\n--- Mimic Mode Stats ---", "cyan")
            cprint(f"Total Requests in Interval: {self._requests_since_last_report}", "cyan")
            cprint(f"Interval Cache Hits: {self.cache_hits} ({hit_percentage:.2f}%)", "green")
            cprint(f"Interval Cache Misses: {self.cache_misses} ({miss_percentage:.2f}%)", "yellow")
            cprint("--------------------------\n", "cyan")

            # Reset interval stats
            self._requests_since_last_report = 0
            self.cache_hits = 0
            self.cache_misses = 0
            self.total_requests = 0


async def periodic_reporter(stats_collector: MimicStatsCollector, shutdown_event: asyncio.Event, interval: int = 60):
    """Periodically calls the report method until a shutdown event is set."""
    while not shutdown_event.is_set():
        try:
            await asyncio.wait_for(shutdown_event.wait(), timeout=interval)
        except asyncio.TimeoutError:
            # This is the normal case, the timeout is our interval
            stats_collector.report()
        except asyncio.CancelledError:
            break
    cprint("Stats reporter stopped.", "blue")
