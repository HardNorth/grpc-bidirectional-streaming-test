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
                yield await item_queue.get()
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
        self.item_start_tracker = ResponseTracker()
        self.item_finish_tracker = ResponseTracker()
        self.generator_tracker = queue.Queue()
        self.start_item_queue = asyncio.queues.Queue()
        self.finish_item_queue = asyncio.queues.Queue()

    async def __aenter__(self):
        self.is_running = True
        self.channel = await grpc.aio.insecure_channel(self.url).__aenter__()
        self.client = reportportal_pb2_grpc.ReportPortalReportingStub(
            self.channel)
        start_item_request_gen = self.test_item_gen(self.start_item_queue)
        start_item_response_gen = self.client.StartTestItemStream(
            start_item_request_gen, wait_for_ready=True)
        self.generator_tracker.put(asyncio.create_task(self.test_item_track(
            start_item_response_gen, 'Item started: ',
            self.item_start_tracker)))
        finish_item_request_gen = self.test_item_gen(self.finish_item_queue)
        finish_item_response_gen = self.client.FinishTestItemStream(
            finish_item_request_gen, wait_for_ready=True)
        self.generator_tracker.put(asyncio.create_task(
            self.test_item_track(finish_item_response_gen,
                                 'Item finished: ',
                                 self.item_finish_tracker)))
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        while not self.start_item_queue.empty() or \
                not self.finish_item_queue.empty():
            await asyncio.sleep(0.1)

        while self.item_start_tracker.size() > 0 and \
                self.item_finish_tracker.size() > 0:
            await asyncio.sleep(0.1)

        while True:
            try:
                generator_task = self.generator_tracker.get_nowait()
                generator_task.cancel()
            except queue.Empty:
                break

        self.is_running = False
        await self.channel.__aexit__(exc_type, exc_val, exc_tb)
        return self

    async def start_launch(self, rq):
        logger.debug('Starting Launch:' + rq.uuid)
        response = await self.client.StartLaunch(rq)
        logger.debug('Launch started: ' + response.uuid)

    async def finish_launch(self, rq):
        logger.debug('Finishing Launch:' + rq.uuid)
        response = await self.client.FinishLaunch(rq)
        logger.debug('Launch finished: ' + response.uuid)

    async def start_item(self, rq):
        self.item_start_tracker.track(rq.uuid)
        logger.debug('Starting Item:' + rq.uuid)
        await self.start_item_queue.put(rq)

    async def finish_item(self, rq):
        self.item_finish_tracker.track(rq.uuid)
        logger.debug('Finishing Item:' + rq.uuid)
        await self.finish_item_queue.put(rq)


async def run(item_number):
    async with ReportPortalClient('localhost:9000') as client:
        launch_uuid = str(uuid.uuid4())
        await client.start_launch(
            reportportal_pb2.StartLaunchRQ(uuid=launch_uuid,
                                           name='Test Launch'))

        for i in range(item_number):
            item_uuid = str(i) + "-" + str(uuid.uuid4())
            await client.start_item(
                reportportal_pb2.StartTestItemRQ(uuid=item_uuid))
            await client.finish_item(
                reportportal_pb2.FinishTestItemRQ(
                    uuid=item_uuid, status=reportportal_pb2.PASSED))

        finish_launch_rq = reportportal_pb2.FinishExecutionRQ(uuid=launch_uuid)
        await client.finish_launch(finish_launch_rq)


if __name__ == '__main__':
    logging.basicConfig(level=logging.INFO)
    start_time = time.time()
    asyncio.run(run(50000))
    logger.info('Finishing the test. Took: {} seconds'.format(
        time.time() - start_time))
    logger.info('Total thread number: ' + str(len(threading.enumerate())))
