package com.epam.reportportal.grpc;

import com.epam.reportportal.grpc.model.*;
import io.quarkus.grpc.GrpcService;
import io.smallrye.mutiny.Multi;
import io.smallrye.mutiny.Uni;

import java.util.Random;
import java.util.concurrent.atomic.AtomicLong;

@GrpcService
public class ReportPortalReportingService implements ReportPortalReporting {

	private static final AtomicLong LAUNCH_COUNTER = new AtomicLong();

	@Override
	public Uni<StartLaunchRS> startLaunch(StartLaunchRQ request) {
		try {
			Thread.sleep(new Random().nextInt(100));
		} catch (InterruptedException e) {
			throw new RuntimeException(e);
		}
		return Uni.createFrom()
				.item(() -> StartLaunchRS.newBuilder()
						.setUuid(request.getUuid())
						.setMessage("OK")
						.setNumber(LAUNCH_COUNTER.incrementAndGet())
						.build());
	}

	@Override
	public Uni<OperationCompletionRS> finishLaunch(FinishExecutionRQ request) {
		try {
			Thread.sleep(new Random().nextInt(50));
		} catch (InterruptedException e) {
			throw new RuntimeException(e);
		}

		return Uni.createFrom()
				.item(() -> OperationCompletionRS.newBuilder().setUuid(request.getUuid()).setMessage("OK").build());
	}

	@Override
	public Multi<ItemCreatedRS> startTestItem(Multi<StartTestItemRQ> request) {
		return Multi.createFrom().emitter(c -> request.subscribe().with(rq -> {
			try {
				Thread.sleep(new Random().nextInt(200));
			} catch (InterruptedException e) {
				c.fail(e);
			}
			c.emit(ItemCreatedRS.newBuilder().setUuid(rq.getUuid()).setMessage("OK").build());
		}));
	}

	@Override
	public Multi<OperationCompletionRS> finishTestItem(Multi<FinishTestItemRQ> request) {
		return Multi.createFrom().emitter(c -> request.subscribe().with(rq -> {
			try {
				Thread.sleep(new Random().nextInt(20));
			} catch (InterruptedException e) {
				c.fail(e);
			}
			c.emit(OperationCompletionRS.newBuilder().setUuid(rq.getUuid()).setMessage("OK").build());
		}));
	}

	@Override
	public Multi<ItemCreatedRS> startNestedItem(Multi<StartNestedItemRQ> request) {
		return Multi.createFrom().emitter(c -> request.subscribe().with(rq -> {
			try {
				Thread.sleep(new Random().nextInt(200));
			} catch (InterruptedException e) {
				c.fail(e);
			}
			c.emit(ItemCreatedRS.newBuilder().setUuid(rq.getUuid()).setMessage("OK").build());
		}));
	}

	@Override
	public Multi<OperationCompletionRS> finishNestedItem(Multi<FinishNestedItemRQ> request) {
		return Multi.createFrom().emitter(c -> request.subscribe().with(rq -> {
			try {
				Thread.sleep(new Random().nextInt(20));
			} catch (InterruptedException e) {
				c.fail(e);
			}
			c.emit(OperationCompletionRS.newBuilder().setUuid(rq.getUuid()).setMessage("OK").build());
		}));
	}
}
