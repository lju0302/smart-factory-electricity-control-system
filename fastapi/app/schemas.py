from pydantic import BaseModel
from typing import Optional, List


class StreamStartRequest(BaseModel):
    start_timestamp: Optional[int] = None
    end_timestamp: Optional[int] = None
    interval_seconds: Optional[float] = None
    chunk_timestamps: Optional[int] = None
    modules: Optional[List[str]] = None
    use_current_event_time: bool = True
    inject_demo_anomaly: bool = False


class StreamStatusResponse(BaseModel):
    is_running: bool
    sent_events: int
    sent_timestamp_groups: int
    current_source_timestamp: Optional[int]
    message: str