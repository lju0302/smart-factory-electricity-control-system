import json
import logging
import os
from datetime import datetime, timezone
from typing import Any

import azure.functions as func
import pyodbc
import requests


app = func.FunctionApp()


# =========================
# 0. DB / HTTP 공통 함수
# =========================

def get_db_connection():
    conn_str = os.environ["SqlOdbcConnectionString"]
    return pyodbc.connect(conn_str)


def safe_str(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, datetime):
        return value.isoformat(sep=" ", timespec="seconds")
    return str(value)


def safe_float(value: Any, default: float = 0.0) -> float:
    if value is None:
        return default
    return float(value)


def send_to_workflow(payload: dict):
    webhook_url = os.environ["TEAMS_ALERT_WEBHOOK_URL"]
    response = requests.post(webhook_url, json=payload, timeout=15)
    response.raise_for_status()


# =========================
# 1. 알림 조회 / 상태 업데이트
# =========================

def load_pending_alerts(cursor) -> list[dict]:
    max_dispatch_count = int(os.environ.get("MAX_DISPATCH_COUNT", "20"))
    max_retry_count = int(os.environ.get("MAX_RETRY_COUNT", "3"))

    cursor.execute(
        """
        SELECT TOP (?)
            alert_id,
            equipment_id,
            window_end_time,
            anomaly_type,
            severity,
            metric_name,
            metric_value,
            threshold_value,
            anomaly_score,
            rule_score,
            iforest_score,
            final_score,
            duration_minutes,
            detection_window,
            message,
            created_at,
            retry_count
        FROM dbo.anomaly_event
        WHERE notification_status IN ('PENDING', 'FAILED')
          AND retry_count < ?
          AND severity IN ('warning', 'critical', 'recovery')
        ORDER BY
            CASE severity
                WHEN 'critical' THEN 1
                WHEN 'warning' THEN 2
                WHEN 'recovery' THEN 3
                ELSE 9
            END,
            created_at ASC
        """,
        max_dispatch_count,
        max_retry_count,
    )

    columns = [col[0] for col in cursor.description]
    return [dict(zip(columns, row)) for row in cursor.fetchall()]


def mark_alert_sent(cursor, alert_id: int):
    cursor.execute(
        """
        UPDATE dbo.anomaly_event
        SET notification_status = 'SENT',
            notified_at = SYSDATETIME(),
            last_error_message = NULL
        WHERE alert_id = ?
        """,
        alert_id,
    )


def mark_alert_failed(cursor, alert_id: int, error_message: str):
    cursor.execute(
        """
        UPDATE dbo.anomaly_event
        SET notification_status = 'FAILED',
            retry_count = retry_count + 1,
            last_error_message = ?
        WHERE alert_id = ?
        """,
        error_message[:1000],
        alert_id,
    )


# =========================
# 2. Teams 알림 메시지 생성
# =========================

def severity_icon(severity: str) -> str:
    if severity == "critical":
        return "🚨"
    if severity == "warning":
        return "⚠️"
    if severity == "recovery":
        return "✅"
    return "ℹ️"


def build_html_alert(alert: dict) -> str:
    icon = severity_icon(safe_str(alert.get("severity")))

    equipment_id = safe_str(alert.get("equipment_id"))
    window_end_time = safe_str(alert.get("window_end_time"))
    anomaly_type = safe_str(alert.get("anomaly_type"))
    severity = safe_str(alert.get("severity"))
    metric_name = safe_str(alert.get("metric_name"))
    metric_value = alert.get("metric_value")
    threshold_value = alert.get("threshold_value")
    anomaly_score = alert.get("anomaly_score")
    rule_score = alert.get("rule_score")
    iforest_score = alert.get("iforest_score")
    final_score = alert.get("final_score")
    duration_minutes = alert.get("duration_minutes")
    detection_window = safe_str(alert.get("detection_window"))
    message = safe_str(alert.get("message"))

    return f"""
    <html>
    <body>
        <h2>{icon} 실시간 설비 이상탐지 알림</h2>

        <h3>[{severity.upper()}] {equipment_id} - {anomaly_type}</h3>

        <table border="1" cellpadding="6" cellspacing="0">
            <tbody>
                <tr><th align="left">설비</th><td>{equipment_id}</td></tr>
                <tr><th align="left">감지 시각</th><td>{window_end_time}</td></tr>
                <tr><th align="left">집계 기준</th><td>{detection_window}</td></tr>
                <tr><th align="left">이상 유형</th><td>{anomaly_type}</td></tr>
                <tr><th align="left">심각도</th><td><b>{severity.upper()}</b></td></tr>
                <tr><th align="left">측정 지표</th><td>{metric_name}</td></tr>
                <tr><th align="left">측정값</th><td>{metric_value}</td></tr>
                <tr><th align="left">기준값</th><td>{threshold_value}</td></tr>
                <tr><th align="left">지속 시간</th><td>{duration_minutes}분</td></tr>
                <tr><th align="left">최종 점수</th><td>{final_score}</td></tr>
                <tr><th align="left">Rule 점수</th><td>{rule_score}</td></tr>
                <tr><th align="left">I-Forest 점수</th><td>{iforest_score}</td></tr>
                <tr><th align="left">모델 이상 점수</th><td>{anomaly_score}</td></tr>
            </tbody>
        </table>

        <h3>해석</h3>
        <p>{message}</p>
    </body>
    </html>
    """


def build_alert_payload(alert: dict) -> dict:
    severity = safe_str(alert.get("severity"))
    equipment_id = safe_str(alert.get("equipment_id"))
    anomaly_type = safe_str(alert.get("anomaly_type"))

    return {
        "alert_id": int(alert["alert_id"]),
        "title": f"[{severity.upper()}] 설비 이상 감지 - {equipment_id}",
        "html": build_html_alert(alert),
        "equipment_id": equipment_id,
        "window_end_time": safe_str(alert.get("window_end_time")),
        "anomaly_type": anomaly_type,
        "severity": severity,
        "metric_name": safe_str(alert.get("metric_name")),
        "metric_value": alert.get("metric_value"),
        "threshold_value": alert.get("threshold_value"),
        "anomaly_score": alert.get("anomaly_score"),
        "rule_score": alert.get("rule_score"),
        "iforest_score": alert.get("iforest_score"),
        "final_score": alert.get("final_score"),
        "duration_minutes": alert.get("duration_minutes"),
        "detection_window": safe_str(alert.get("detection_window")),
        "message": safe_str(alert.get("message")),
    }


# =========================
# 3. Alert Dispatcher
# =========================

def dispatch_pending_alerts() -> dict:
    conn = get_db_connection()
    cursor = conn.cursor()

    sent_count = 0
    failed_count = 0
    skipped_count = 0

    try:
        alerts = load_pending_alerts(cursor)
        logging.info("Pending alerts loaded. count=%s", len(alerts))

        for alert in alerts:
            alert_id = int(alert["alert_id"])

            try:
                payload = build_alert_payload(alert)
                send_to_workflow(payload)
                mark_alert_sent(cursor, alert_id)
                conn.commit()

                sent_count += 1
                logging.info("Alert sent. alert_id=%s", alert_id)

            except Exception as e:
                mark_alert_failed(cursor, alert_id, str(e))
                conn.commit()

                failed_count += 1
                logging.exception("Alert dispatch failed. alert_id=%s", alert_id)

        return {
            "sent_count": sent_count,
            "failed_count": failed_count,
            "skipped_count": skipped_count,
            "checked_at": datetime.now(timezone.utc).isoformat(),
        }

    finally:
        cursor.close()
        conn.close()


# =========================
# 4. Timer Trigger
# =========================
# NCRONTAB: 초 분 시 일 월 요일
# 기본값: 1분마다 PENDING 알림 발송 시도
# 실제 운영에서 15분 탐지 앱과 분리한다면 Dispatcher는 1~5분 주기가 좋음.

@app.function_name(name="DispatchAnomalyAlertsTimer")
@app.timer_trigger(
    schedule="%ALERT_DISPATCH_CRON%",
    arg_name="timer",
    run_on_startup=False,
    use_monitor=True
)
def dispatch_anomaly_alerts_timer(timer: func.TimerRequest) -> None:
    logging.info("DispatchAnomalyAlertsTimer started.")

    result = dispatch_pending_alerts()

    logging.info("DispatchAnomalyAlertsTimer finished. result=%s", json.dumps(result, ensure_ascii=False))


# # =========================
# # 5. 로컬/시연용 HTTP 수동 실행
# # =========================
# # Azure 배포 시 필요 없으면 삭제 가능.
# # POST /api/DispatchAnomalyAlertsManual

# @app.function_name(name="DispatchAnomalyAlertsManual")
# @app.route(route="DispatchAnomalyAlertsManual", methods=["POST"], auth_level=func.AuthLevel.FUNCTION)
# def dispatch_anomaly_alerts_manual(req: func.HttpRequest) -> func.HttpResponse:
#     logging.info("DispatchAnomalyAlertsManual started.")

#     try:
#         result = dispatch_pending_alerts()
#         return func.HttpResponse(
#             json.dumps(result, ensure_ascii=False),
#             status_code=200,
#             mimetype="application/json"
#         )

#     except Exception as e:
#         logging.exception("Manual dispatch failed.")
#         return func.HttpResponse(
#             json.dumps({"error": str(e)}, ensure_ascii=False),
#             status_code=500,
#             mimetype="application/json"
#         )
