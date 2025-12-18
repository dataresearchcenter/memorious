"""
Memorious procrastinate task definitions.

This module defines a single task that handles all crawler stage executions.
The task receives the stage payload, executes the appropriate operation,
and defers new tasks for subsequent stages.
"""

from typing import Any

from anystore.logging import get_logger
from openaleph_procrastinate.app import App, make_app
from openaleph_procrastinate.model import DatasetJob
from openaleph_procrastinate.tasks import task

from memorious.logic.crawler import get_crawler

log = get_logger(__name__)

# Create the procrastinate app
app: App = make_app("memorious.tasks")


@task(app=app, retry=3)
def execute_stage(job: DatasetJob) -> None:
    """
    Execute a single crawler stage.

    This is the main entry point for all crawler operations. It:
    1. Loads the crawler configuration
    2. Creates an execution context
    3. Executes the stage method
    4. The context.emit() calls will defer new jobs for subsequent stages

    Payload fields:
        - stage: Stage name to execute
        - run_id: Unique run identifier
        - incremental: Whether to skip already-processed items
        - continue_on_error: Whether to continue on errors
        - data: Stage input data dict
    """
    # Import here to avoid circular import with context.py
    from memorious.logic.context import Context

    payload = job.payload
    dataset = job.dataset
    stage_name = payload["stage"]
    run_id = payload["run_id"]

    # Load crawler from config file URI
    crawler = get_crawler(payload["config_file"])

    stage = crawler.get(stage_name)
    if stage is None:
        job.log.error(f"Stage not found: `{stage_name}`")
        return

    # Create execution context with state
    state = {
        "dataset": dataset,
        "run_id": run_id,
        "incremental": payload.get("incremental", True),
        "continue_on_error": payload.get("continue_on_error", False),
    }
    context = Context(crawler, stage, state)

    # Execute the stage
    try:
        context.execute(payload.get("data", {}))
    except Exception:
        if not payload.get("continue_on_error", False):
            # TODO: cacnel dataset
            raise


def defer_stage(
    dataset: str,
    stage: str,
    run_id: str,
    config_file: str,
    data: dict[str, Any],
    incremental: bool = True,
    continue_on_error: bool = False,
    priority: int = 50,
) -> None:
    """
    Defer a new stage execution job.

    This is called by Context.emit() to queue subsequent stages.
    """
    job = DatasetJob(
        queue="memorious",
        task="memorious.tasks.execute_stage",
        dataset=dataset,
        payload={
            "stage": stage,
            "run_id": run_id,
            "config_file": config_file,
            "incremental": incremental,
            "continue_on_error": continue_on_error,
            "data": data,
        },
    )
    with app.open():
        job.defer(app, priority=priority)
