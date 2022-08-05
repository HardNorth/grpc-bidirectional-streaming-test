package com.epam.reportportal.grpc;

import com.epam.reportportal.grpc.model.*;
import io.grpc.ManagedChannel;
import io.grpc.ManagedChannelBuilder;
import io.smallrye.mutiny.Multi;
import io.smallrye.mutiny.subscription.Cancellable;
import org.reactivestreams.Publisher;
import org.reactivestreams.Subscriber;
import org.reactivestreams.Subscription;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;

import java.util.Queue;
import java.util.UUID;
import java.util.concurrent.BlockingQueue;
import java.util.concurrent.ConcurrentLinkedQueue;
import java.util.concurrent.LinkedBlockingQueue;
import java.util.concurrent.TimeUnit;
import java.util.concurrent.atomic.AtomicInteger;

public class ReportPortalReportingAppSingleEndpoint {

	private static final Logger LOGGER = LoggerFactory.getLogger(ReportPortalReportingAppSingleEndpoint.class);

	public static class ThreadedPublisher<T> extends Thread implements Subscription, Publisher<T> {

		private final BlockingQueue<T> queue;

		private final Queue<Subscriber<? super T>> subscribers = new ConcurrentLinkedQueue<>();

		private volatile boolean running = true;

		public ThreadedPublisher(BlockingQueue<T> publishingQueue) {
			queue = publishingQueue;
		}

		@Override
		public void run() {
			try {
				T item;
				while (running && (item = queue.poll(200, TimeUnit.MILLISECONDS)) != null) {
					for (Subscriber<? super T> s : subscribers) {
						s.onNext(item);
					}
				}
			} catch (InterruptedException exc) {
				subscribers.forEach(s -> s.onError(exc));
			}
			subscribers.forEach(Subscriber::onComplete);
		}

		@Override
		public void subscribe(Subscriber<? super T> s) {
			subscribers.add(s);
			s.onSubscribe(this);
		}

		@Override
		public void request(long n) {
			start();
		}

		@Override
		public void cancel() {
			running = false;
		}
	}

	public static class ReportingApp {

		private final AtomicInteger itemProcessed = new AtomicInteger();

		private final ManagedChannel channel = ManagedChannelBuilder.forAddress("localhost", 9000)
				.usePlaintext()
				.build();

		ReportPortalReporting rpService = new ReportPortalReportingClient("Report Portal Client",
				channel,
				(n, c) -> c.withWaitForReady()
		);

		private final BlockingQueue<EntityRQ> entryQueue = new LinkedBlockingQueue<>();

		private void logLaunch(StartLaunchRS response) {
			LOGGER.info("Launch started: " + response.getUuid());
		}

		private void logCompletion(OperationCompletionRS response) {
			itemProcessed.incrementAndGet();
			LOGGER.info(response.getType() + " Item finished: " + response.getUuid());
		}

		private void logLaunchCompletion(OperationCompletionRS response) {
			LOGGER.info("Launch finished: " + response.getUuid());
		}

		private void logError(Throwable throwable) {
			throwable.printStackTrace();
		}

		public void run(int number) {
			LOGGER.warn("Starting test");
			String launchUuid = UUID.randomUUID().toString();
			Cancellable startLaunchSubscriber = rpService.startLaunch(StartLaunchRQ.newBuilder()
					.setUuid(launchUuid)
					.setName("Test Launch")
					.build()).subscribe().with(this::logLaunch, this::logError);

			ThreadedPublisher<EntityRQ> entryPublisher = new ThreadedPublisher<>(entryQueue);
			Multi<EntityRQ> entryEmitter = Multi.createFrom().publisher(entryPublisher);
			Cancellable itemSubscriber = rpService.uploadStream(entryEmitter)
					.subscribe()
					.with(this::logCompletion, this::logError);

			for (int i = 0; i < number; i++) {
				String itemUuid = i + "-" + UUID.randomUUID();
				entryQueue.add(EntityRQ.newBuilder()
						.setUuid(itemUuid)
						.setStartItemRq(StartTestItemRQ.newBuilder().setUuid(itemUuid).build())
						.build());
				entryQueue.add(EntityRQ.newBuilder()
						.setUuid(itemUuid)
						.setFinishItemRq(FinishTestItemRQ.newBuilder().setUuid(itemUuid).build())
						.build());
			}

			Cancellable finishLaunchSubscriber = rpService.finishLaunch(FinishExecutionRQ.newBuilder()
					.setUuid(launchUuid)
					.build()).subscribe().with(this::logLaunchCompletion, this::logError);

			while (itemProcessed.get() < number) {
				try {
					Thread.sleep(1);
				} catch (InterruptedException e) {
					break;
				}
			}

			LOGGER.warn("Test finished");

			startLaunchSubscriber.cancel();
			itemSubscriber.cancel();
			finishLaunchSubscriber.cancel();
			channel.shutdown();
		}
	}

	public static void main(String... args) {
		long startTime = System.currentTimeMillis();
		new ReportingApp().run(50);
		LOGGER.warn(String.format("Finishing the test. Took: %f seconds%n",
				(System.currentTimeMillis() - startTime) / 1000f
		));
	}
}
