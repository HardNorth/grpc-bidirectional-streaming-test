import asyncio
import logging
import queue
import threading
import time
import uuid

import grpc

from reportportal_grpc_client.client import reportportal_pb2_grpc, \
    reportportal_pb2

logger = logging.getLogger(__name__)


class ResponseTracker:
    def __init__(self):
        self.items = dict()

    def acknowledge(self, item):
        if len(self.items) > 0:
            if item in self.items.keys():
                del self.items[item]

    def size(self):
        return len(self.items)

    def track(self, item):
        self.items[item] = True


# noinspection PyCompatibility
class ReportPortalClient:

    async def test_item_gen(self, item_queue):
        while self.is_running:
            try:
                item = item_queue.get_nowait()
                yield item
            except asyncio.queues.QueueEmpty:
                try:
                    await asyncio.sleep(0.01)
                except asyncio.CancelledError:
                    break

    async def test_item_track(self, generator, message, tracker):
        while self.is_running:
            try:
                item = await generator.read()
                if item == grpc.aio.EOF:
                    logger.debug('Channel closed, exiting...')
                    break
                logger.debug(message + item.uuid)
                if tracker:
                    tracker.acknowledge(item.uuid)
            except asyncio.CancelledError:
                logger.debug('Generator halted, exiting...')
                break

    def __init__(self, url):
        self.is_running = False
        self.url = url
        self.loop = asyncio.get_event_loop()
        self.thread = threading.Thread(target=self.loop.run_forever,
                                       name='Async-Report',
                                       daemon=True)
        self.item_start_tracker = ResponseTracker()
        self.item_finish_tracker = ResponseTracker()
        self.task_queue = queue.Queue()
        self.generator_tracker = queue.Queue()
        self.start_item_queue = asyncio.queues.Queue()
        self.finish_item_queue = asyncio.queues.Queue()

    def __enter__(self):
        self.is_running = True
        self.channel = self.loop.run_until_complete(
            grpc.aio.insecure_channel(self.url).__aenter__())
        self.client = reportportal_pb2_grpc.ReportPortalReportingStub(
            self.channel)
        start_item_request_gen = self.test_item_gen(self.start_item_queue)
        start_item_response_gen = self.client.StartTestItem(
            start_item_request_gen, wait_for_ready=True)
        self.generator_tracker.put(self.loop.create_task(self.test_item_track(
            start_item_response_gen, 'Item started: ',
            self.item_start_tracker)))
        finish_item_request_gen = self.test_item_gen(self.finish_item_queue)
        finish_item_response_gen = self.client.FinishTestItem(
            finish_item_request_gen, wait_for_ready=True)
        self.generator_tracker.put(self.loop.create_task(
            self.test_item_track(finish_item_response_gen,
                                 'Item finished: ',
                                 self.item_finish_tracker)))
        self.thread.start()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        while self.item_start_tracker.size() > 0 and \
                self.item_finish_tracker.size() > 0:
            time.sleep(0.1)
        tear_down_start = time.time()
        first_task = None
        while time.time() - tear_down_start < 10:
            try:
                task = self.task_queue.get_nowait()
                if not first_task:
                    first_task = task
                if task.done():
                    if task == first_task:
                        first_task = None
                else:
                    self.task_queue.put_nowait(task)
                    if task == first_task:
                        time.sleep(0.1)
            except queue.Empty:
                break

        while True:
            try:
                task = self.task_queue.get_nowait()
                task.cancel()
            except queue.Empty:
                break

        while True:
            try:
                generator_task = self.generator_tracker.get_nowait()
                generator_task.cancel()
            except queue.Empty:
                break

        self.is_running = False
        channel_close_task = self.loop.create_task(
            self.channel.__aexit__(exc_type, exc_val, exc_tb))
        while not channel_close_task.done():
            time.sleep(0.1)
        self.loop.stop()

        # FIXME: For some reason the loop never stops, find out why
        # while self.loop.is_running():
        #     time.sleep(0.1)
        # self.loop.close()
        return self

    async def start_launch_async(self, rq):
        logger.debug('Starting Launch:' + rq.uuid)
        response = await self.client.StartLaunch(rq)
        logger.debug('Launch started: ' + response.uuid)

    async def finish_launch_async(self, rq):
        logger.debug('Finishing Launch:' + rq.uuid)
        response = await self.client.FinishLaunch(rq)
        logger.debug('Launch finished: ' + response.uuid)

    async def start_item_async(self, rq):
        self.item_start_tracker.track(rq.uuid)
        logger.debug('Starting Item:' + rq.uuid)
        await self.start_item_queue.put(rq)

    async def finish_item_async(self, rq):
        self.item_finish_tracker.track(rq.uuid)
        logger.debug('Finishing Item:' + rq.uuid)
        await self.finish_item_queue.put(rq)

    def start_launch(self, rq):
        self.task_queue.put(
            self.loop.create_task(self.start_launch_async(rq)))

    def finish_launch(self, rq):
        self.task_queue.put(
            self.loop.create_task(self.finish_launch_async(rq)))

    def start_item(self, rq):
        self.task_queue.put(
            self.loop.create_task(self.start_item_async(rq)))

    def finish_item(self, rq):
        self.task_queue.put(
            self.loop.create_task(self.finish_item_async(rq)))


def run(item_number):
    with ReportPortalClient('localhost:9000') as client:
        launch_uuid = str(uuid.uuid4())
        client.start_launch(reportportal_pb2.StartLaunchRQ(uuid=launch_uuid,
                                                           name='Test Launch'))

        for i in range(item_number):
            item_uuid = str(i) + "-" + str(uuid.uuid4())
            client.start_item(
                reportportal_pb2.StartTestItemRQ(uuid=item_uuid))
            client.finish_item(
                reportportal_pb2.FinishTestItemRQ(
                    uuid=item_uuid, status=reportportal_pb2.PASSED))

        finish_launch_rq = reportportal_pb2.FinishExecutionRQ(uuid=launch_uuid)
        client.finish_launch(finish_launch_rq)


if __name__ == '__main__':
    logging.basicConfig(level=logging.INFO)
    start_time = time.time()
    run(500)
    logger.info('Finishing the test. Took: {} seconds'.format(
        time.time() - start_time))
    logger.info('Total thread number: ' + str(len(threading.enumerate())))
