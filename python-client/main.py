import grpc
import logging
from reportportal_grpc_client.client import reportportal_pb2_grpc

def run():
    with grpc.insecure_channel('localhost:9000') as channel:
        stub = reportportal_pb2_grpc.ReportPortalReportingStub(channel)
        response = stub.StartLaunch(reportportal_pb2_grpc)
    print("Greeter client received: " + response.message)


if __name__ == '__main__':
    logging.basicConfig()
    run()
