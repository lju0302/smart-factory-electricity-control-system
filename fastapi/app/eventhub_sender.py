import json
from datetime import datetime, timezone
from typing import List, Dict, Any

from azure.eventhub.aio import EventHubProducerClient
from azure.eventhub import EventData


class EventHubSender:
    def __init__(
        self,
        connection_str: str,
        eventhub_name: str,
        dry_run: bool = True,
    ):
        self.connection_str = connection_str
        self.eventhub_name = eventhub_name
        self.dry_run = dry_run
        self.client = None

    async def __aenter__(self):
        if not self.dry_run:
            self.client = EventHubProducerClient.from_connection_string(
                conn_str=self.connection_str,
                eventhub_name=self.eventhub_name,
            )
        return self

    async def __aexit__(self, exc_type, exc, tb):
        if self.client is not None:
            await self.client.close()

    async def send_events(self, events: List[Dict[str, Any]]) -> int:
        if not events:
            return 0

        if self.dry_run:
            print(f"[DRY_RUN] sending {len(events)} events")
            print(json.dumps(events[0], ensure_ascii=False, indent=2))
            return len(events)

        event_batch = await self.client.create_batch()

        sent_count = 0

        for event in events:
            payload = json.dumps(event, ensure_ascii=False)
            event_data = EventData(payload)

            try:
                event_batch.add(event_data)
            except ValueError:
                await self.client.send_batch(event_batch)
                sent_count += len(event_batch)

                event_batch = await self.client.create_batch()
                event_batch.add(event_data)

        if len(event_batch) > 0:
            await self.client.send_batch(event_batch)
            sent_count += len(event_batch)

        return sent_count


def dataframe_to_events(df, use_current_event_time: bool = True) -> List[Dict[str, Any]]:
    events = []

    now_iso = datetime.now(timezone.utc).isoformat()

    for _, row in df.iterrows():
        if use_current_event_time:
            event_time = now_iso
        else:
            event_time = str(row.get("localtime"))

        event = {
            "event_time": event_time,
            "source_timestamp": int(row["timestamp"]),
            "localtime": int(row["localtime"]),
            "module": str(row["module"]),

            "voltageR": float(row["voltageR"]),
            "voltageS": float(row["voltageS"]),
            "voltageT": float(row["voltageT"]),
            "voltageRS": float(row["voltageRS"]),
            "voltageST": float(row["voltageST"]),
            "voltageTR": float(row["voltageTR"]),

            "currentR": float(row["currentR"]),
            "currentS": float(row["currentS"]),
            "currentT": float(row["currentT"]),

            "activePower": float(row["activePower"]),

            "powerFactorR": float(row["powerFactorR"]),
            "powerFactorS": float(row["powerFactorS"]),
            "powerFactorT": float(row["powerFactorT"]),

            "reactivePowerLagging": float(row["reactivePowerLagging"]),
            "accumActiveEnergy": float(row["accumActiveEnergy"]),

            "synthetic_anomaly": bool(row.get("synthetic_anomaly", False)),
            "synthetic_anomaly_type": str(row.get("synthetic_anomaly_type", "normal")),
        }

        events.append(event)

    return events