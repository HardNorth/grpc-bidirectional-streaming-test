package com.epam.reportportal.grpc;

import com.epam.reportportal.grpc.model.*;
import io.grpc.ManagedChannel;
import io.grpc.ManagedChannelBuilder;
import io.smallrye.mutiny.Multi;
import io.smallrye.mutiny.subscription.Cancellable;
import org.reactivestreams.Publisher;
import org.reactivestreams.Subscriber;
import org.reactivestreams.Subscription;

import java.util.Queue;
import java.util.UUID;
import java.util.concurrent.BlockingQueue;
import java.util.concurrent.ConcurrentLinkedQueue;
import java.util.concurrent.LinkedBlockingQueue;
import java.util.concurrent.TimeUnit;

public class ReportPortalReportingApp {

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
				Thread.sleep(100);
				T item;
				while (running && (item = queue.poll(10, TimeUnit.MILLISECONDS)) != null) {
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

		private final ManagedChannel channel = ManagedChannelBuilder.forAddress("localhost", 9000)
				.usePlaintext()
				.build();

		ReportPortalReporting rpService = new ReportPortalReportingClient("Report Portal Client",
				channel,
				(n, c) -> c.withWaitForReady()
		);

		private final BlockingQueue<StartTestItemRQ> itemStartQueue = new LinkedBlockingQueue<>();

		private final BlockingQueue<FinishTestItemRQ> itemFinishQueue = new LinkedBlockingQueue<>();

		private void logLaunch(StartLaunchRS response) {
			System.out.println("Launch started: " + response.getUuid());
		}

		private void logItemStart(ItemCreatedRS response) {
			System.out.println("Item started: " + response.getUuid());
		}

		private void logCompletion(OperationCompletionRS response) {
			System.out.println("Item finished: " + response.getUuid());
		}

		private void logLaunchCompletion(OperationCompletionRS response) {
			System.out.println("Launch finished: " + response.getUuid());
		}

		private void logError(Throwable throwable) {
			throwable.printStackTrace();
		}

		public void run() throws InterruptedException {
			System.out.println("Starting test");
			String launchUuid = UUID.randomUUID().toString();
			Cancellable startLaunchSubscriber = rpService.startLaunch(StartLaunchRQ.newBuilder()
					.setUuid(launchUuid)
					.setName("Test Launch")
					.build()).subscribe().with(this::logLaunch, this::logError);

			ThreadedPublisher<StartTestItemRQ> startPublisher = new ThreadedPublisher<>(itemStartQueue);
			Multi<StartTestItemRQ> startEmitter = Multi.createFrom().publisher(startPublisher);
			Cancellable startSubscriber = rpService.startTestItem(startEmitter)
					.subscribe()
					.with(this::logItemStart, this::logError);

			ThreadedPublisher<FinishTestItemRQ> finishPublisher = new ThreadedPublisher<>(itemFinishQueue);
			Multi<FinishTestItemRQ> finishEmitter = Multi.createFrom().publisher(finishPublisher);
			Cancellable finishSubscriber = rpService.finishTestItem(finishEmitter)
					.subscribe()
					.with(this::logCompletion, this::logError);

			for (int i = 0; i < 50; i++) {
				String itemUuid = i + "-" + UUID.randomUUID();
				itemStartQueue.add(StartTestItemRQ.newBuilder().setUuid(itemUuid).build());
				itemFinishQueue.add(FinishTestItemRQ.newBuilder()
						.setUuid(itemUuid)
						.setStatus(ItemStatus.PASSED)
						.build());
			}

			Thread.sleep(10000);

			Cancellable finishLaunchSubscriber = rpService.finishLaunch(FinishExecutionRQ.newBuilder()
					.setUuid(launchUuid)
					.build()).subscribe().with(this::logLaunchCompletion, this::logError);

			System.out.println("Test finished");

			Thread.sleep(100);
			startLaunchSubscriber.cancel();
			startSubscriber.cancel();
			finishSubscriber.cancel();
			finishLaunchSubscriber.cancel();
			channel.shutdown();
			if (!channel.awaitTermination(5, TimeUnit.SECONDS)) {
				System.out.println("Unable to shut down channel");
				channel.shutdownNow();
			}
		}
	}

	public static void main(String... args) throws Exception {
		new ReportingApp().run();
	}
}
