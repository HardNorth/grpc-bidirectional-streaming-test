import asyncio
import logging
import queue
import threading
import time
import uuid

import grpc

from reportportal_grpc_client.client import reportportal_pb2_grpc, \
    reportportal_pb2

class ResponseTracker:

    def __init__(self):
        self.items = dict()
        self._lock = threading.Lock()

    def acknowledge(self, item):
        with self._lock:
            if len(self.items) > 0:
                if item in self.items.keys():
                    del self.items[item]

    def size(self):
        with self._lock:
            return len(self.items)

    def track(self, item):
        with self._lock:
            self.items[item] = True


# noinspection PyCompatibility
class ReportPortalClient:

    async def test_item_gen(self, item_queue):
        yield await item_queue.get()

    async def test_item_track(self, generator, message, tracker):
        async for item in generator:
            print(message + item.uuid)
            tracker.acknowledge(item.uuid)

    def __init__(self, url):
        self.url = url
        self.loop = asyncio.new_event_loop()
        self.item_start_tracker = ResponseTracker()
        self.item_finish_tracker = ResponseTracker()
        self.task_tracker = queue.Queue()
        self.start_item_queue = asyncio.queues.Queue()
        self.finish_item_queue = asyncio.queues.Queue()

    def __enter__(self):
        self.channel = self.loop.run_until_complete(
            grpc.aio.insecure_channel(self.url).__aenter__())
        self.client = reportportal_pb2_grpc.ReportPortalReportingStub(
            self.channel)
        self.task_tracker.put(self.loop.create_task(self.test_item_track(
            self.client.StartTestItem(
                self.test_item_gen(self.start_item_queue)), "Item started: ",
            self.item_start_tracker)))
        self.task_tracker.put(self.loop.create_task(
            self.test_item_track(self.client.FinishTestItem(
                self.test_item_gen(self.finish_item_queue)), "Item finished: ",
                self.item_finish_tracker)))
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        while self.item_start_tracker.size() > 0 and \
                self.item_finish_tracker.size() > 0:
            time.sleep(0.1)
        self.loop.close()
        self.channel.__aexit__(exc_type, exc_val, exc_tb)
        return self

    async def start_launch_async(self, rq):
        response = await self.client.StartLaunch(rq)
        print('Launch started: ' + response.uuid)

    async def finish_launch_async(self, rq):
        response = await self.client.FinishLaunch(rq)
        print('Launch finished: ' + response.uuid)

    async def start_item_async(self, rq):
        await self.start_item_queue.put(rq)

    async def finish_item_async(self, rq):
        await self.finish_item_queue.put(rq)

    def start_launch(self, rq):
        self.task_tracker.put(
            self.loop.create_task(self.start_launch_async(rq)))

    def finish_launch(self, rq):
        self.task_tracker.put(
            self.loop.create_task(self.finish_launch_async(rq)))

    def start_item(self, rq):
        self.item_start_tracker.track(rq.uuid)
        self.task_tracker.put(
            self.loop.create_task(self.start_item_async(rq)))

    def finish_item(self, rq):
        self.item_finish_tracker.track(rq.uuid)
        self.task_tracker.put(
            self.loop.create_task(self.finish_item_async(rq)))


def run(item_number):
    with ReportPortalClient('localhost:9000') as client:
        launch_uuid = str(uuid.uuid4())
        client.start_launch(reportportal_pb2.StartLaunchRQ(uuid=launch_uuid,
                                                           name='Test Launch'))

        for i in range(item_number):
            item_uuid = str(i) + "-" + str(uuid.uuid4())
            reportportal_pb2.StartTestItemRQ(uuid=item_uuid)
            client.start_item(
                reportportal_pb2.StartTestItemRQ(uuid=item_uuid))
            client.finish_item(
                reportportal_pb2.FinishTestItemRQ(
                    uuid=item_uuid, status=reportportal_pb2.PASSED))

        finish_launch_rq = reportportal_pb2.FinishExecutionRQ(uuid=launch_uuid)
        client.finish_launch(finish_launch_rq)


if __name__ == '__main__':
    logging.basicConfig()
    start_time = time.time()
    run(5000)
    print('Finishing the test. Took: {} seconds'.format(
        time.time() - start_time))
