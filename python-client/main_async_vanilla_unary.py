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

    def __init__(self, url):
        self.is_running = False
        self.url = url
        self.item_start_tracker = ResponseTracker()
        self.item_finish_tracker = ResponseTracker()
        self.generator_tracker = queue.Queue()

    async def __aenter__(self):
        self.is_running = True
        self.channel = await grpc.aio.insecure_channel(self.url).__aenter__()
        self.client = reportportal_pb2_grpc.ReportPortalReportingStub(
            self.channel)
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        while self.item_start_tracker.size() > 0 and \
                self.item_finish_tracker.size() > 0:
            await asyncio.sleep(0.1)

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
        response = await self.client.StartTestItem(rq)
        self.item_start_tracker.acknowledge(response.uuid)
        logger.debug('Item started:' + response.uuid)

    async def finish_item(self, rq):
        self.item_finish_tracker.track(rq.uuid)
        logger.debug('Finishing Item:' + rq.uuid)
        response = await self.client.FinishTestItem(rq)
        self.item_finish_tracker.acknowledge(response.uuid)
        logger.debug('Item finished:' + response.uuid)


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
    asyncio.run(run(50))
    logger.info('Finishing the test. Took: {} seconds'.format(
        time.time() - start_time))
    logger.info('Total thread number: ' + str(len(threading.enumerate())))
