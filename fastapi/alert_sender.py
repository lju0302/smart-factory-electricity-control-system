import logging
import os
from typing import Any

import requests


def safe_float(value: Any, default: float = 0.0) -> float:
    try:
        if value is None:
            return default
        return float(value)
    except Exception:
        return default


def safe_int(value: Any, default: int = 0) -> int:
    try:
        if value is None:
            return default
        return int(value)
    except Exception:
        return default


def safe_str(value: Any, default: str = "") -> str:
    if value is None:
        return default
    return str(value)


def should_send_alert(pred: dict) -> bool:
    level = safe_str(pred.get("final_anomaly_level"), "normal").lower()
    return level in ("warning", "critical")


def build_alert_html(pred: dict) -> str:
    level = safe_str(pred.get("final_anomaly_level"), "normal").lower()
    equipment_id = safe_str(pred.get("equipment_id"))
    window_end_time = safe_str(pred.get("window_end_time"))
    aggregation_level = safe_str(pred.get("aggregation_level"))

    final_score = safe_float(pred.get("final_anomaly_score"))
    rule_score = safe_float(pred.get("rule_score"))
    iforest_score = safe_float(pred.get("iforest_score"))
    rule_contribution = safe_float(pred.get("rule_contribution"))
    iforest_contribution = safe_float(pred.get("iforest_contribution"))

    primary_model = safe_str(pred.get("primary_anomaly_model"))
    model_vote_count = safe_int(pred.get("model_vote_count"))
    rule_reason = safe_str(pred.get("rule_reason"))

    final_reason = safe_str(pred.get("final_reason"))
    recommended_action = safe_str(pred.get("recommended_action"))

    data_quality_flag = safe_int(pred.get("data_quality_issue_flag"))
    data_quality_reason = safe_str(pred.get("data_quality_reason"))

    icon = "🚨" if level == "critical" else "⚠️"

    return f"""
    <html>
    <body>
        <h2>{icon} 실시간 설비 이상탐지 알림</h2>

        <h3>[{level.upper()}] {equipment_id}</h3>

        <table border="1" cellpadding="6" cellspacing="0">
            <tbody>
                <tr><th align="left">설비</th><td>{equipment_id}</td></tr>
                <tr><th align="left">감지 시각</th><td>{window_end_time}</td></tr>
                <tr><th align="left">집계 기준</th><td>{aggregation_level}</td></tr>
                <tr><th align="left">심각도</th><td><b>{level.upper()}</b></td></tr>
                <tr><th align="left">최종 이상 점수</th><td>{final_score:.2f}</td></tr>
                <tr><th align="left">Rule 점수</th><td>{rule_score:.2f}</td></tr>
                <tr><th align="left">Isolation Forest 점수</th><td>{iforest_score:.2f}</td></tr>
                <tr><th align="left">Rule 기여도</th><td>{rule_contribution:.2f}</td></tr>
                <tr><th align="left">I-Forest 기여도</th><td>{iforest_contribution:.2f}</td></tr>
                <tr><th align="left">주요 판정 방식</th><td>{primary_model}</td></tr>
                <tr><th align="left">모델 Vote 수</th><td>{model_vote_count}</td></tr>
                <tr><th align="left">Rule 사유</th><td>{rule_reason}</td></tr>
                <tr><th align="left">데이터 품질 플래그</th><td>{data_quality_flag}</td></tr>
                <tr><th align="left">데이터 품질 사유</th><td>{data_quality_reason}</td></tr>
            </tbody>
        </table>

        <h3>판정 사유</h3>
        <p>{final_reason}</p>

        <h3>권장 조치</h3>
        <p>{recommended_action}</p>
    </body>
    </html>
    """


def build_alert_payload(pred: dict) -> dict:
    level = safe_str(pred.get("final_anomaly_level"), "normal").lower()
    equipment_id = safe_str(pred.get("equipment_id"))

    return {
        "title": f"[{level.upper()}] 설비 이상 감지 - {equipment_id}",
        "html": build_alert_html(pred),
        "equipment_id": equipment_id,
        "window_end_time": safe_str(pred.get("window_end_time")),
        "aggregation_level": safe_str(pred.get("aggregation_level")),
        "severity": level,
        "final_anomaly_score": safe_float(pred.get("final_anomaly_score")),
        "rule_score": safe_float(pred.get("rule_score")),
        "iforest_score": safe_float(pred.get("iforest_score")),
        "rule_contribution": safe_float(pred.get("rule_contribution")),
        "iforest_contribution": safe_float(pred.get("iforest_contribution")),
        "primary_anomaly_model": safe_str(pred.get("primary_anomaly_model")),
        "model_vote_count": safe_int(pred.get("model_vote_count")),
        "rule_reason": safe_str(pred.get("rule_reason")),
        "final_reason": safe_str(pred.get("final_reason")),
        "recommended_action": safe_str(pred.get("recommended_action")),
        "data_quality_issue_flag": safe_int(pred.get("data_quality_issue_flag")),
        "data_quality_reason": safe_str(pred.get("data_quality_reason")),
    }


def send_alerts_to_teams(predictions_list: list[dict]) -> dict:
    webhook_url = os.environ.get("TEAMS_ALERT_WEBHOOK_URL")

    if not webhook_url:
        logging.warning("TEAMS_ALERT_WEBHOOK_URL is missing. Skipping Teams alert.")
        return {
            "sent_count": 0,
            "skipped_count": len(predictions_list),
            "failed_count": 0,
        }

    sent_count = 0
    skipped_count = 0
    failed_count = 0

    for pred in predictions_list:
        level = safe_str(pred.get("final_anomaly_level"), "normal").lower()

        if not should_send_alert(pred):
            skipped_count += 1
            continue

        try:
            payload = build_alert_payload(pred)
            response = requests.post(webhook_url, json=payload, timeout=15)
            response.raise_for_status()

            sent_count += 1

            logging.info(
                "Teams alert sent. equipment_id=%s, level=%s, final_score=%s",
                pred.get("equipment_id"),
                level,
                pred.get("final_anomaly_score"),
            )

        except Exception as alert_err:
            failed_count += 1
            logging.error(
                "Failed to send Teams alert. equipment_id=%s, level=%s, error=%s",
                pred.get("equipment_id"),
                level,
                str(alert_err),
            )

    logging.info(
        "Teams alert finished. sent=%s, skipped=%s, failed=%s",
        sent_count,
        skipped_count,
        failed_count,
    )

    return {
        "sent_count": sent_count,
        "skipped_count": skipped_count,
        "failed_count": failed_count,
    }
