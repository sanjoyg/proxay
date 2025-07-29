import asyncio
from unittest.mock import patch, MagicMock

import pytest

from proxay import stats


def test_stats_collector_counts():
    """Tests that the collector correctly counts hits and misses."""
    collector = stats.MimicStatsCollector()
    collector.record_hit()
    collector.record_hit()
    collector.record_miss()

    assert collector.total_requests == 3
    assert collector.cache_hits == 2
    assert collector.cache_misses == 1
    assert collector._requests_since_last_report == 3


@patch("sys.stdout.write")
def test_stats_collector_report_verbose(mock_stdout_write):
    """Tests the report formatting and reset logic in verbose mode."""
    collector = stats.MimicStatsCollector(verbose=True)
    collector.record_hit()
    collector.record_miss()
    collector.report()

    output = "".join(call.args[0] for call in mock_stdout_write.call_args_list)
    assert "Mimic Mode Stats" in output
    assert "Total Requests in Interval: 2" in output
    assert "Interval Cache Hits: 1 (50.00%)" in output
    assert "Interval Cache Misses: 1 (50.00%)" in output

    assert collector._requests_since_last_report == 0


@patch("sys.stdout.write")
def test_stats_collector_report_not_verbose(mock_stdout_write):
    """Tests that no report is printed when not in verbose mode."""
    collector = stats.MimicStatsCollector(verbose=False)
    collector.record_hit()
    collector.report()

    mock_stdout_write.assert_not_called()
    assert collector.total_requests == 1


@pytest.mark.asyncio
async def test_periodic_reporter():
    """Tests that the periodic reporter calls report() and can be shut down."""

    shutdown_event = asyncio.Event()
    collector = MagicMock(spec=stats.MimicStatsCollector)

    async def run_reporter():
        await stats.periodic_reporter(collector, shutdown_event, interval=0.01)

    task = asyncio.create_task(run_reporter())

    # Let it run for a short time
    await asyncio.sleep(0.05)

    # Signal shutdown
    shutdown_event.set()

    # Wait for the task to finish
    await task

    # Check that report was called at least once
    collector.report.assert_called()
    assert collector.report.call_count > 0
