import os
import logging
import pyodbc
import azure.functions as func

app = func.FunctionApp()


def get_db_connection():
    conn_str = os.environ["SQL_CONNECTION_STRING"]
    return pyodbc.connect(conn_str)


@app.timer_trigger(
    schedule="0 0 * * * *",
    arg_name="myTimer",
    run_on_startup=False,
    use_monitor=True
)
def HourlyAggregateTimer(myTimer: func.TimerRequest) -> None:
    logging.info("[HourlyAggregateTimer] 1시간 집계 타이머 트리거 시작")

    if myTimer.past_due:
        logging.warning("[HourlyAggregateTimer] 타이머가 지연 실행되었습니다.")

    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("EXEC dbo.usp_timer_aggregate_1h;")
            conn.commit()

        logging.info("[HourlyAggregateTimer] 1시간 집계 프로시저 실행 완료")

    except Exception as e:
        logging.exception(f"[HourlyAggregateTimer] 1시간 집계 프로시저 실행 실패: {e}")
        raise


@app.timer_trigger(
    schedule="0 5 15 * * *",
    arg_name="myTimer",
    run_on_startup=False,
    use_monitor=True
)
def DailyAggregateTimer(myTimer: func.TimerRequest) -> None:
    logging.info("[DailyAggregateTimer] 1일 집계 타이머 트리거 시작")

    if myTimer.past_due:
        logging.warning("[DailyAggregateTimer] 타이머가 지연 실행되었습니다.")

    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("EXEC dbo.usp_timer_aggregate_1d;")
            conn.commit()

        logging.info("[DailyAggregateTimer] 1일 집계 + reportstatus 작성 완료")

    except Exception as e:
        logging.exception(f"[DailyAggregateTimer] 1일 집계 프로시저 실행 실패: {e}")
        raise