import asyncio
from typing import Optional, List

from app.data_loader import PowerDataLoader
from app.eventhub_sender import EventHubSender, dataframe_to_events
from app.anomaly_injector import AnomalyInjector


class StreamManager:
    def __init__(
        self,
        data_loader: PowerDataLoader,
        eventhub_sender: EventHubSender,
        default_interval_seconds: float = 0.5,
        default_chunk_timestamps: int = 20,
    ):
        self.data_loader = data_loader
        self.eventhub_sender = eventhub_sender
        self.default_interval_seconds = default_interval_seconds
        self.default_chunk_timestamps = default_chunk_timestamps

        self.is_running = False
        self.task: Optional[asyncio.Task] = None

        self.sent_events = 0
        self.sent_timestamp_groups = 0
        self.current_source_timestamp: Optional[int] = None

        self.anomaly_injector = AnomalyInjector()

    async def start(
        self,
        start_timestamp: Optional[int] = None,
        end_timestamp: Optional[int] = None,
        interval_seconds: Optional[float] = None,
        chunk_timestamps: Optional[int] = None,
        modules: Optional[List[str]] = None,
        use_current_event_time: bool = True,
        inject_demo_anomaly: bool = False,
    ):
        if self.is_running:
            raise RuntimeError("Stream is already running.")

        self.is_running = True
        self.sent_events = 0
        self.sent_timestamp_groups = 0
        self.current_source_timestamp = start_timestamp

        self.task = asyncio.create_task(
            self._run_stream(
                start_timestamp=start_timestamp,
                end_timestamp=end_timestamp,
                interval_seconds=interval_seconds or self.default_interval_seconds,
                chunk_timestamps=chunk_timestamps or self.default_chunk_timestamps,
                modules=modules,
                use_current_event_time=use_current_event_time,
                inject_demo_anomaly=inject_demo_anomaly,
            )
        )

    async def stop(self):
        self.is_running = False

        if self.task is not None:
            self.task.cancel()
            try:
                await self.task
            except asyncio.CancelledError:
                pass

        self.task = None

    async def _run_stream(
        self,
        start_timestamp: Optional[int],
        end_timestamp: Optional[int],
        interval_seconds: float,
        chunk_timestamps: int,
        modules: Optional[List[str]],
        use_current_event_time: bool,
        inject_demo_anomaly: bool,
    ):
        last_timestamp = start_timestamp

        try:
            async with self.eventhub_sender as sender:
                while self.is_running:
                    df = self.data_loader.get_next_chunk(
                        last_timestamp=last_timestamp,
                        chunk_timestamps=chunk_timestamps,
                        end_timestamp=end_timestamp,
                        modules=modules,
                    )

                    if df.empty:
                        self.is_running = False
                        break

                    if inject_demo_anomaly:
                        df = self.anomaly_injector.inject_demo_anomaly(df)

                    for source_timestamp, group_df in df.groupby("timestamp"):
                        if not self.is_running:
                            break

                        events = dataframe_to_events(
                            group_df,
                            use_current_event_time=use_current_event_time,
                        )

                        sent = await sender.send_events(events)

                        self.sent_events += sent
                        self.sent_timestamp_groups += 1
                        self.current_source_timestamp = int(source_timestamp)
                        last_timestamp = int(source_timestamp)

                        await asyncio.sleep(interval_seconds)

        except asyncio.CancelledError:
            raise
        except Exception as e:
            self.is_running = False
            print(f"[STREAM_ERROR] {e}")
            raise