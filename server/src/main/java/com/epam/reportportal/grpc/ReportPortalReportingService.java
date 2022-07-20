package com.epam.reportportal.grpc;

import com.epam.reportportal.grpc.model.*;
import io.quarkus.grpc.GrpcService;
import io.smallrye.mutiny.Multi;
import io.smallrye.mutiny.Uni;
import io.smallrye.mutiny.subscription.MultiEmitter;

import java.util.Random;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;
import java.util.concurrent.atomic.AtomicLong;

@GrpcService
public class ReportPortalReportingService implements ReportPortalReporting {

	private static final AtomicLong LAUNCH_COUNTER = new AtomicLong();

	private static final AtomicLong THREAD_COUNTER = new AtomicLong();

	private final ExecutorService executorService = Executors.newFixedThreadPool(100, r -> {
		Thread t = new Thread(r);
		t.setDaemon(true);
		t.setName("Worker-thread-" + THREAD_COUNTER.incrementAndGet());
		return t;
	});

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

	private static <T> Runnable createJob(T response, MultiEmitter<? super T> emitter) {
		return () -> {
			try {
				Thread.sleep(new Random().nextInt(200));
			} catch (InterruptedException e) {
				emitter.fail(e);
			}
			emitter.emit(response);
		};
	}

	@Override
	public Multi<ItemCreatedRS> startTestItem(Multi<StartTestItemRQ> request) {
		return Multi.createFrom().emitter(c -> request.subscribe().with(rq -> {
			var uuid = rq.getUuid();
			Runnable task = createJob(ItemCreatedRS.newBuilder().setUuid(uuid).setMessage("OK").build(), c);
			executorService.submit(task);
		}));
	}

	@Override
	public Multi<OperationCompletionRS> finishTestItem(Multi<FinishTestItemRQ> request) {
		return Multi.createFrom().emitter(c -> request.subscribe().with(rq -> {
			var uuid = rq.getUuid();
			Runnable task = createJob(OperationCompletionRS.newBuilder().setUuid(uuid).setMessage("OK").build(), c);
			executorService.submit(task);
		}));
	}
}
