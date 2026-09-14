import json
import logging
import os
from datetime import datetime

import azure.functions as func
import pymssql

import score
from alert_sender import send_alerts_to_teams

app = func.FunctionApp()

score.init()
logging.info("Azure Functions Anomaly Detection Model initialized successfully.")


def get_db_config():
    server = os.environ.get("DB_SERVER")
    database = os.environ.get("DB_DATABASE")
    user = os.environ.get("DB_USER")
    password = os.environ.get("DB_PASSWORD")

    if not all([server, database, user, password]):
        raise ValueError("DB Connection environment variables are missing.")

    return server, database, user, password


def safe_float(value, default=0.0):
    try:
        if value is None:
            return default
        return float(value)
    except Exception:
        return default


def safe_int(value, default=0):
    try:
        if value is None:
            return default
        return int(value)
    except Exception:
        return default


def safe_bit(value):
    if isinstance(value, bool):
        return 1 if value else 0
    return safe_int(value, 0)


def parse_datetime_value(value):
    if value is None:
        return None

    if isinstance(value, datetime):
        return value.replace(tzinfo=None)

    try:
        value_str = str(value).replace("Z", "+00:00")
        return datetime.fromisoformat(value_str).replace(tzinfo=None)
    except Exception:
        return None


def insert_predictions_to_db(predictions_list):
    """
    score.py 결과를 anomaly_predictions 테이블에 저장합니다.
    """
    try:
        server, database, user, password = get_db_config()
    except Exception as env_err:
        logging.error(str(env_err))
        return

    conn = None
    try:
        conn = pymssql.connect(
            server=server,
            user=user,
            password=password,
            database=database,
            timeout=10,
        )
        cursor = conn.cursor()

        insert_query = """
            INSERT INTO [anomaly_predictions] (
                equipment_id,
                window_end_time,
                final_anomaly_score,
                final_anomaly_level,
                strong_anomaly_candidate,
                critical_candidate,
                final_reason,
                recommended_action,
                aggregation_level,
                rule_anomaly,
                rule_score,
                rule_reason,
                iforest_anomaly,
                iforest_score,
                primary_anomaly_model,
                model_vote_count,
                rule_contribution,
                iforest_contribution,
                data_quality_issue_flag,
                data_quality_reason,
                created_at,
                reference_only
            ) VALUES (
                %s, %s, %s, %s, %s, %s, %s, %s,
                %s, %s, %s, %s, %s, %s, %s, %s,
                %s, %s, %s, %s, %s, %s
            )
        """

        records_to_insert = []
        for idx, pred in enumerate(predictions_list):
            window_end_time = parse_datetime_value(pred.get("window_end_time"))
            if window_end_time is None:
                logging.error(
                    "Skipping prediction with invalid window_end_time. index=%s equipment_id=%s window_end_time=%r",
                    idx,
                    pred.get("equipment_id"),
                    pred.get("window_end_time"),
                )
                continue

            records_to_insert.append(
                (
                    pred.get("equipment_id"),
                    window_end_time,
                    safe_float(pred.get("final_anomaly_score")),
                    pred.get("final_anomaly_level", "normal"),
                    safe_int(pred.get("strong_anomaly_candidate")),
                    safe_int(pred.get("critical_candidate")),
                    pred.get("final_reason"),
                    pred.get("recommended_action"),
                    pred.get("aggregation_level"),
                    safe_int(pred.get("rule_anomaly")),
                    safe_float(pred.get("rule_score")),
                    pred.get("rule_reason"),
                    safe_int(pred.get("iforest_anomaly")),
                    safe_float(pred.get("iforest_score")),
                    pred.get("primary_anomaly_model"),
                    safe_int(pred.get("model_vote_count")),
                    safe_float(pred.get("rule_contribution")),
                    safe_float(pred.get("iforest_contribution")),
                    safe_int(pred.get("data_quality_issue_flag")),
                    pred.get("data_quality_reason"),
                    parse_datetime_value(pred.get("created_at")),
                    safe_bit(pred.get("reference_only")),
                )
            )

        if not records_to_insert:
            logging.info("No prediction records to insert.")
            return

        cursor.executemany(insert_query, records_to_insert)
        conn.commit()
        logging.info(
            "Successfully inserted %s records to DB with extended anomaly columns.",
            len(records_to_insert),
        )
    except Exception as db_err:
        logging.error("Failed to insert data to Database: %s", str(db_err))
        if conn:
            conn.rollback()
    finally:
        if conn:
            conn.close()


@app.event_hub_message_trigger(
    arg_name="azeventhub",
    event_hub_name="%AnomalyEventHubName%",
    connection="EventHubConnectionString",
    consumer_group="%AnomalyConsumerGroupName%",
)
def event_hub_trigger(azeventhub: func.EventHubEvent):
    try:
        raw_body = azeventhub.get_body().decode("utf-8")
        logging.info("Received batch data from Event Hub: %s", raw_body)

        raw_body_stripped = raw_body.strip()
        if raw_body_stripped.startswith("[") and raw_body_stripped.endswith("]"):
            payload = json.loads(raw_body_stripped)
        else:
            payload = [json.loads(line) for line in raw_body_stripped.split("\n") if line.strip()]

        predictions = score.run(payload)

        if "error" in predictions:
            logging.error("Inference error: %s", predictions["error"])
            return

        prediction_rows = predictions.get("predictions", [])

        if not prediction_rows:
            logging.warning("No predictions returned from score.run().")
            return

        logging.info("Calculated predictions. Writing to Database...")
        insert_predictions_to_db(prediction_rows)

        alert_result = send_alerts_to_teams(prediction_rows)
        logging.info(
            "Teams alert summary. sent=%s, skipped=%s, failed=%s",
            alert_result["sent_count"],
            alert_result["skipped_count"],
            alert_result["failed_count"],
        )
    except Exception as e:
        logging.error("Error executing Azure Function: %s", str(e))
