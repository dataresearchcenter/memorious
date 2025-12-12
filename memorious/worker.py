import structlog
from servicelayer.logs import apply_task_context
from servicelayer.worker import Worker

from memorious.core import conn
from memorious.logic.context import Context
from memorious.logic.stage import CrawlerStage

log = structlog.get_logger(__name__)


class MemoriousWorker(Worker):
    def __init__(self, conn, crawler, manager, num_threads=None):
        super().__init__(conn=conn, num_threads=num_threads)
        self.crawler = crawler
        self.manager = manager

    def handle(self, task):
        apply_task_context(task)
        data = task.payload
        stage = CrawlerStage.detach_namespace(task.stage.stage)
        state = task.context
        context = Context.from_state(state, stage, self.manager)
        context.execute(data)

    def after_task(self, task):
        if task.job.is_done():
            stage = CrawlerStage.detach_namespace(task.stage.stage)
            state = task.context
            context = Context.from_state(state, stage, self.manager)
            context.crawler.aggregate(context)

    def get_stages(self):
        return [stage.namespaced_name for stage in self.crawler.stages.values()]


def get_worker(crawler, manager, num_threads=None):
    return MemoriousWorker(
        conn=conn, crawler=crawler, manager=manager, num_threads=num_threads
    )
