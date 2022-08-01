import logging
import threading
import time
import uuid
from queue import Queue, Empty

import grpc

from reportportal_grpc_client.client import reportportal_pb2_grpc, \
    reportportal_pb2

IS_RUNNING = True

START_ITEM_QUEUE = Queue()
FINISH_ITEM_QUEUE = Queue()

logger = logging.getLogger(__name__)


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


def process_incoming_messages(generator, message, tracker):
    try:
        for item in generator:
            item_uuid = item.uuid
            logger.debug(message + item.uuid)
            tracker.acknowledge(item_uuid)
    except grpc.RpcError as exc:
        code = exc.code()
        if code is grpc.StatusCode.CANCELLED:
            logger.debug("Computation finished with: " + exc.details())
        else:
            logger.debug("ERROR: " + str(exc))


def start_test_item_gen():
    while IS_RUNNING:
        try:
            yield START_ITEM_QUEUE.get(timeout=0.1)
        except Empty:
            pass


def finish_test_item_gen():
    while IS_RUNNING:
        try:
            yield FINISH_ITEM_QUEUE.get(timeout=0.1)
        except Empty:
            pass


def run(item_number):
    with grpc.insecure_channel('localhost:9000') as channel:
        stub = reportportal_pb2_grpc.ReportPortalReportingStub(channel)
        launch_uuid = str(uuid.uuid4())
        start_launch_rq = reportportal_pb2.StartLaunchRQ(uuid=launch_uuid,
                                                         name='Test Launch')
        launch_start_rs = stub.StartLaunch(start_launch_rq)
        logger.debug('Launch started: ' + launch_start_rs.uuid)

        item_start_rs_stream = stub.StartTestItemStream(start_test_item_gen(),
                                                        wait_for_ready=True)

        item_finish_rs_stream = stub.FinishTestItemStream(
            finish_test_item_gen(),
            wait_for_ready=True)

        start_rs_tracker = ResponseTracker()
        finish_rs_tracker = ResponseTracker()
        start_rs_worker = threading.Thread(target=process_incoming_messages,
                                           args=(item_start_rs_stream,
                                                 "Item started: ",
                                                 start_rs_tracker))
        finish_rs_worker = threading.Thread(target=process_incoming_messages,
                                            args=(item_finish_rs_stream,
                                                  "Item finished: ",
                                                  finish_rs_tracker))
        start_rs_worker.start()
        finish_rs_worker.start()

        for i in range(item_number):
            item_uuid = str(i) + "-" + str(uuid.uuid4())
            start_rs_tracker.track(item_uuid)
            finish_rs_tracker.track(item_uuid)
            reportportal_pb2.StartTestItemRQ(uuid=item_uuid)
            START_ITEM_QUEUE.put(
                reportportal_pb2.StartTestItemRQ(uuid=item_uuid))
            FINISH_ITEM_QUEUE.put(
                reportportal_pb2.FinishTestItemRQ(
                    uuid=item_uuid, status=reportportal_pb2.PASSED))

        finish_launch_rq = reportportal_pb2.FinishExecutionRQ(uuid=launch_uuid)
        launch_finish_rs = stub.FinishLaunch(finish_launch_rq)
        logger.debug('Launch finished: ' + launch_finish_rs.uuid)

        while start_rs_tracker.size() > 0 and finish_rs_tracker.size() > 0:
            time.sleep(0.1)

        global IS_RUNNING
        IS_RUNNING = False


if __name__ == '__main__':
    test_number = 50000
    logging.basicConfig(level=logging.INFO)
    start_time = time.time()
    run(test_number)
    logger.info(
        'Finishing the test of {} items. Took: {} seconds'
        .format(test_number, time.time() - start_time))
    logger.info('Total thread number: ' + str(len(threading.enumerate())))
