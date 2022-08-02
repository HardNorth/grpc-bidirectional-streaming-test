package com.epam.reportportal.rest;

import com.epam.reportportal.grpc.model.*;
import io.smallrye.mutiny.Uni;
import io.smallrye.mutiny.subscription.MultiEmitter;
import io.smallrye.mutiny.subscription.UniEmitter;

import javax.ws.rs.POST;
import javax.ws.rs.PUT;
import javax.ws.rs.Path;
import java.util.Random;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;
import java.util.concurrent.atomic.AtomicLong;

@Path("/api")
public class ReportPortalReportingService {

	private static final AtomicLong LAUNCH_COUNTER = new AtomicLong();

	private static final AtomicLong THREAD_COUNTER = new AtomicLong();

	private final ExecutorService executorService = Executors.newFixedThreadPool(100, r -> {
		Thread t = new Thread(r);
		t.setDaemon(true);
		t.setName("Worker-thread-" + THREAD_COUNTER.incrementAndGet());
		return t;
	});

	@POST
	@Path("/launch")
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

	@PUT
	@Path("/launch")
	public Uni<OperationCompletionRS> finishLaunch(FinishExecutionRQ request) {
		try {
			Thread.sleep(new Random().nextInt(50));
		} catch (InterruptedException e) {
			throw new RuntimeException(e);
		}

		return Uni.createFrom()
				.item(() -> OperationCompletionRS.newBuilder().setUuid(request.getUuid()).setMessage("OK").build());
	}

	private static <T> Runnable createJob(T response, UniEmitter<? super T> emitter) {
		return () -> {
			try {
				Thread.sleep(new Random().nextInt(200));
			} catch (InterruptedException e) {
				emitter.fail(e);
			}
			emitter.complete(response);
		};
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

	@POST
	@Path("/item")
	public Uni<ItemCreatedRS> startTestItem(StartTestItemRQ request) {
		return Uni.createFrom().emitter(c -> {
			var uuid = request.getUuid();
			Runnable task = createJob(ItemCreatedRS.newBuilder().setUuid(uuid).setMessage("OK").build(), c);
			executorService.submit(task);
		});
	}

	@PUT
	@Path("/item")
	public Uni<OperationCompletionRS> finishTestItem(FinishTestItemRQ request) {
		return Uni.createFrom().emitter(c -> {
			var uuid = request.getUuid();
			Runnable task = createJob(OperationCompletionRS.newBuilder().setUuid(uuid).setMessage("OK").build(), c);
			executorService.submit(task);
		});
	}
}
