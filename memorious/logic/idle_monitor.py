"""Idle monitor for auto-stopping workers when queue becomes idle."""

import asyncio

from anystore.logging import get_logger
from procrastinate.worker import Worker

log = get_logger(__name__)


class IdleMonitor:
    """Monitor job queue and stop worker after idle timeout.

    The monitor polls the job queue and tracks when it becomes idle
    (no pending or running jobs). After a configurable timeout of
    continuous idleness, it stops the worker gracefully.
    """

    def __init__(
        self,
        app,
        worker: Worker,
        queue: str = "memorious",
        idle_timeout: int = 30,
        poll_interval: int = 2,
    ):
        """Initialize the idle monitor.

        Args:
            app: Procrastinate App instance.
            worker: Worker instance to stop when idle.
            queue: Queue name to monitor.
            idle_timeout: Seconds of continuous idleness before stopping.
            poll_interval: Seconds between queue checks.
        """
        self.app = app
        self.worker = worker
        self.queue = queue
        self.idle_timeout = idle_timeout
        self.poll_interval = poll_interval
        self._idle_since: float | None = None

    async def is_queue_idle(self) -> bool:
        """Check if no pending (TODO) or running (DOING) jobs.

        Returns:
            True if the queue has no pending or running jobs.
        """
        # Check for TODO jobs
        todo_jobs = await self.app.job_manager.list_jobs_async(
            queue=self.queue, status="todo"
        )
        if todo_jobs:
            return False

        # Check for DOING jobs
        doing_jobs = await self.app.job_manager.list_jobs_async(
            queue=self.queue, status="doing"
        )
        if doing_jobs:
            return False

        return True

    async def run(self) -> None:
        """Run the idle monitor loop.

        Monitors the queue and stops the worker when idle threshold is reached.
        """
        log.info(
            "Starting idle monitor",
            idle_timeout=self.idle_timeout,
            poll_interval=self.poll_interval,
            queue=self.queue,
        )

        loop = asyncio.get_event_loop()

        while True:
            # Check if worker was already stopped
            if self.worker._stop_event.is_set():
                log.debug("Worker already stopped, exiting monitor")
                break

            try:
                is_idle = await self.is_queue_idle()
            except Exception as e:
                log.warning("Error checking queue status", error=str(e))
                is_idle = False

            current_time = loop.time()

            if is_idle:
                if self._idle_since is None:
                    self._idle_since = current_time
                    log.debug("Queue became idle", idle_since=self._idle_since)

                idle_duration = current_time - self._idle_since

                if idle_duration >= self.idle_timeout:
                    log.info(
                        "Idle timeout reached, stopping worker",
                        idle_duration=idle_duration,
                        idle_timeout=self.idle_timeout,
                    )
                    self.worker.stop()
                    break
            else:
                if self._idle_since is not None:
                    log.debug("Queue became active again")
                self._idle_since = None

            await asyncio.sleep(self.poll_interval)
