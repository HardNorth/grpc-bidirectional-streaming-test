import time
import threading
import logging
import uuid
from queue import Queue, Empty

import grpc

from reportportal_grpc_client.client import reportportal_pb2_grpc, \
    reportportal_pb2

IS_RUNNING = True

START_ITEM_QUEUE = Queue()
FINISH_ITEM_QUEUE = Queue()


class Worker(threading.Thread):

    def __init__(self, generator, message):
        super().__init__()
        self.generator = generator
        self.message = message

    def run(self):
        try:
            for item in self.generator:
                print(self.message + item.uuid)
        except grpc.RpcError as exc:
            code = exc.code()
            if code is grpc.StatusCode.CANCELLED:
                print("Computation finished with: " + exc.details())
            else:
                print("ERROR: " + str(exc))


def start_test_item_gen():
    while IS_RUNNING:
        try:
            yield START_ITEM_QUEUE.get(timeout=0.1)
        except Empty:
            pass


def finish_test_item_gen():
    while IS_RUNNING:
        try:
            yield START_ITEM_QUEUE.get(timeout=0.1)
        except Empty:
            pass


def run():
    with grpc.insecure_channel('localhost:9000') as channel:
        stub = reportportal_pb2_grpc.ReportPortalReportingStub(channel)
        launch_uuid = str(uuid.uuid4())
        start_launch_rq = reportportal_pb2.StartLaunchRQ(uuid=launch_uuid,
                                                         name='Test Launch')
        launch_start_rs = stub.StartLaunch(start_launch_rq)
        print('Launch started: ' + launch_start_rs.uuid)

        item_start_rs_stream = stub.StartTestItem(start_test_item_gen(),
                                                  wait_for_ready=True)

        item_finish_rs_stream = stub.FinishTestItem(finish_test_item_gen(),
                                                    wait_for_ready=True)

        start_rs_worker = Worker(item_start_rs_stream, "Item started: ")
        finish_rs_worker = Worker(item_finish_rs_stream, "Item finished: ")
        start_rs_worker.start()
        finish_rs_worker.start()

        for i in range(50):
            item_uuid = str(i) + "-" + str(uuid.uuid4())
            reportportal_pb2.StartTestItemRQ(uuid=item_uuid)
            START_ITEM_QUEUE.put(
                reportportal_pb2.StartTestItemRQ(uuid=item_uuid))
            FINISH_ITEM_QUEUE.put(
                reportportal_pb2.FinishTestItemRQ(
                    uuid=item_uuid, status=reportportal_pb2.PASSED))

        finish_launch_rq = reportportal_pb2.FinishExecutionRQ(uuid=launch_uuid)
        launch_finish_rs = stub.FinishLaunch(finish_launch_rq)
        print('Launch finished: ' + launch_finish_rs.uuid)

        time.sleep(0.5)

        global IS_RUNNING
        IS_RUNNING = False


if __name__ == '__main__':
    logging.basicConfig()
    run()
    print("Finishing the test")
