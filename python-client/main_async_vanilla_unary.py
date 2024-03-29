import asyncio
import logging
import threading
import time
import uuid

import grpc

from reportportal_grpc_client.client import reportportal_pb2_grpc, \
    reportportal_pb2

logger = logging.getLogger(__name__)


# noinspection PyCompatibility
class ReportPortalClient:

    def __init__(self, url):
        self.url = url

    async def __aenter__(self):
        self.channel = await grpc.aio.insecure_channel(self.url).__aenter__()
        self.client = reportportal_pb2_grpc.ReportPortalReportingStub(
            self.channel)
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
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
        logger.debug('Starting Item:' + rq.uuid)
        response = await self.client.StartTestItem(rq)
        logger.debug('Item started:' + response.uuid)

    async def finish_item(self, rq):
        logger.debug('Finishing Item:' + rq.uuid)
        response = await self.client.FinishTestItem(rq)
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
    test_number = 500
    logging.basicConfig(level=logging.INFO)
    start_time = time.time()
    asyncio.run(run(test_number))
    logger.info(
        'Finishing the test of {} items. Took: {} seconds'
        .format(test_number, time.time() - start_time))
    logger.info('Total thread number: ' + str(len(threading.enumerate())))
