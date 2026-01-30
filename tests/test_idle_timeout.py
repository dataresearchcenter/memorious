"""Tests for idle timeout functionality."""

import asyncio
from unittest.mock import MagicMock, patch

import pytest

from memorious.logic.idle_monitor import IdleMonitor


class MockWorker:
    """Mock worker for testing."""

    def __init__(self):
        self._stop_event = MagicMock()
        self._stop_event.is_set.return_value = False
        self.stopped = False

    def stop(self):
        self.stopped = True
        self._stop_event.is_set.return_value = True


class MockJobManager:
    """Mock job manager for testing."""

    def __init__(self):
        self.todo_jobs = []
        self.doing_jobs = []

    async def list_jobs_async(self, queue=None, status=None):
        if status == "todo":
            return self.todo_jobs
        elif status == "doing":
            return self.doing_jobs
        return []


class MockApp:
    """Mock procrastinate app for testing."""

    def __init__(self):
        self.job_manager = MockJobManager()


class TestIdleMonitor:
    """Test cases for IdleMonitor class."""

    @pytest.mark.asyncio
    async def test_is_queue_idle_when_empty(self):
        """Test that queue is considered idle when empty."""
        app = MockApp()
        worker = MockWorker()
        monitor = IdleMonitor(app, worker, idle_timeout=5)

        is_idle = await monitor.is_queue_idle()
        assert is_idle is True

    @pytest.mark.asyncio
    async def test_is_queue_idle_with_todo_jobs(self):
        """Test that queue is not idle when TODO jobs exist."""
        app = MockApp()
        app.job_manager.todo_jobs = [{"id": 1}]
        worker = MockWorker()
        monitor = IdleMonitor(app, worker, idle_timeout=5)

        is_idle = await monitor.is_queue_idle()
        assert is_idle is False

    @pytest.mark.asyncio
    async def test_is_queue_idle_with_doing_jobs(self):
        """Test that queue is not idle when DOING jobs exist."""
        app = MockApp()
        app.job_manager.doing_jobs = [{"id": 1}]
        worker = MockWorker()
        monitor = IdleMonitor(app, worker, idle_timeout=5)

        is_idle = await monitor.is_queue_idle()
        assert is_idle is False

    @pytest.mark.asyncio
    async def test_stops_worker_after_idle_timeout(self):
        """Test that worker is stopped after idle timeout."""
        app = MockApp()
        worker = MockWorker()
        monitor = IdleMonitor(app, worker, idle_timeout=0.1, poll_interval=0.05)

        # Run monitor (should stop worker after ~0.1s of idleness)
        await asyncio.wait_for(monitor.run(), timeout=2.0)

        assert worker.stopped is True

    @pytest.mark.asyncio
    async def test_resets_idle_timer_on_activity(self):
        """Test that idle timer resets when jobs appear."""
        app = MockApp()
        worker = MockWorker()
        monitor = IdleMonitor(app, worker, idle_timeout=0.2, poll_interval=0.05)

        # After 2 poll cycles, add a job to reset the timer
        async def add_job_later():
            await asyncio.sleep(0.1)
            app.job_manager.todo_jobs = [{"id": 1}]
            await asyncio.sleep(0.1)
            app.job_manager.todo_jobs = []  # Remove to let it become idle again

        asyncio.create_task(add_job_later())

        # Monitor should take longer due to timer reset
        await asyncio.wait_for(monitor.run(), timeout=2.0)

        assert worker.stopped is True

    @pytest.mark.asyncio
    async def test_exits_if_worker_already_stopped(self):
        """Test that monitor exits if worker is already stopped."""
        app = MockApp()
        worker = MockWorker()
        worker._stop_event.is_set.return_value = True  # Already stopped
        monitor = IdleMonitor(app, worker, idle_timeout=5.0, poll_interval=0.01)

        # Should exit immediately
        await asyncio.wait_for(monitor.run(), timeout=0.5)
        # Should not have called stop() since already stopped
        assert worker.stopped is False


class TestCrawlerIdleTimeout:
    """Test Crawler.run() with idle_timeout parameter."""

    def test_idle_timeout_auto_enabled_for_concurrency(self, crawler_dir):
        """Test that idle_timeout is auto-enabled for concurrency > 1."""
        import os

        from memorious.logic.crawler import Crawler

        source_file = os.path.join(crawler_dir, "simple_web_scraper.yml")
        crawler = Crawler(source_file)

        # Mock the _run_with_idle_monitor to capture the call
        with patch.object(crawler, "_run_with_idle_monitor") as mock_run:
            with patch.object(crawler, "start"):
                with patch.object(crawler, "aggregate"):
                    crawler.run(concurrency=4)

            # Should have been called with default 30s timeout
            mock_run.assert_called_once()
            call_kwargs = mock_run.call_args.kwargs
            assert call_kwargs["idle_timeout"] == 30
            assert call_kwargs["concurrency"] == 4

    def test_idle_timeout_disabled_for_single_concurrency(self, crawler_dir):
        """Test that idle_timeout is not auto-enabled for concurrency=1."""
        import os

        from memorious.logic.crawler import Crawler
        from memorious.tasks import app

        source_file = os.path.join(crawler_dir, "simple_web_scraper.yml")
        crawler = Crawler(source_file)

        with patch.object(crawler, "_run_with_idle_monitor") as mock_idle:
            with patch.object(app, "run_worker") as mock_worker:
                with patch.object(crawler, "start"):
                    with patch.object(crawler, "aggregate"):
                        crawler.run(concurrency=1)

            # Should NOT have used idle monitor
            mock_idle.assert_not_called()
            # Should have called regular run_worker
            mock_worker.assert_called_once()

    def test_idle_timeout_explicit_disable(self, crawler_dir):
        """Test that idle_timeout=0 explicitly disables auto-stop."""
        import os

        from memorious.logic.crawler import Crawler
        from memorious.tasks import app

        source_file = os.path.join(crawler_dir, "simple_web_scraper.yml")
        crawler = Crawler(source_file)

        with patch.object(crawler, "_run_with_idle_monitor") as mock_idle:
            with patch.object(app, "run_worker"):
                with patch.object(crawler, "start"):
                    with patch.object(crawler, "aggregate"):
                        # Even with concurrency > 1, idle_timeout=0 disables it
                        crawler.run(concurrency=4, idle_timeout=0)

            # Should NOT have used idle monitor
            mock_idle.assert_not_called()

    def test_idle_timeout_explicit_value(self, crawler_dir):
        """Test that explicit idle_timeout value is used with wait=True."""
        import os

        from memorious.logic.crawler import Crawler

        source_file = os.path.join(crawler_dir, "simple_web_scraper.yml")
        crawler = Crawler(source_file)

        with patch.object(crawler, "_run_with_idle_monitor") as mock_run:
            with patch.object(crawler, "start"):
                with patch.object(crawler, "aggregate"):
                    # idle_timeout only applies when wait=True
                    crawler.run(concurrency=1, wait=True, idle_timeout=10)

            mock_run.assert_called_once()
            call_kwargs = mock_run.call_args.kwargs
            assert call_kwargs["idle_timeout"] == 10
