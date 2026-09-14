from fastapi import FastAPI, HTTPException

from app.config import get_settings
from app.schemas import StreamStartRequest, StreamStatusResponse
from app.data_loader import PowerDataLoader
from app.eventhub_sender import EventHubSender
from app.stream_manager import StreamManager


settings = get_settings()

app = FastAPI(
    title="Smart Factory Power Stream Producer",
    description="5초 단위 설비 전력 데이터를 Event Hub로 재생하는 FastAPI Producer",
    version="0.1.0",
)

data_loader = PowerDataLoader(
    duckdb_path=settings.duckdb_path,
    table_name=settings.duckdb_table,
)

eventhub_sender = EventHubSender(
    connection_str=settings.eventhub_connection_str,
    eventhub_name=settings.eventhub_name,
    dry_run=settings.dry_run,
)

stream_manager = StreamManager(
    data_loader=data_loader,
    eventhub_sender=eventhub_sender,
    default_interval_seconds=settings.default_interval_seconds,
    default_chunk_timestamps=settings.default_chunk_timestamps,
)


@app.get("/health")
def health_check():
    return {
        "status": "ok",
        "dry_run": settings.dry_run,
        "duckdb_path": settings.duckdb_path,
        "duckdb_table": settings.duckdb_table,
    }


@app.get("/sample")
def get_sample(limit: int = 10):
    try:
        df = data_loader.get_sample(limit=limit)
        return {
            "count": len(df),
            "data": df.to_dict(orient="records"),
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/stream/start")
async def start_stream(request: StreamStartRequest):
    try:
        await stream_manager.start(
            start_timestamp=request.start_timestamp,
            end_timestamp=request.end_timestamp,
            interval_seconds=request.interval_seconds,
            chunk_timestamps=request.chunk_timestamps,
            modules=request.modules,
            use_current_event_time=request.use_current_event_time,
            inject_demo_anomaly=request.inject_demo_anomaly,
        )

        return {
            "message": "stream started",
            "dry_run": settings.dry_run,
        }

    except RuntimeError as e:
        raise HTTPException(status_code=409, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/stream/stop")
async def stop_stream():
    await stream_manager.stop()
    return {"message": "stream stopped"}


@app.get("/stream/status", response_model=StreamStatusResponse)
def stream_status():
    return StreamStatusResponse(
        is_running=stream_manager.is_running,
        sent_events=stream_manager.sent_events,
        sent_timestamp_groups=stream_manager.sent_timestamp_groups,
        current_source_timestamp=stream_manager.current_source_timestamp,
        message="running" if stream_manager.is_running else "stopped",
    )