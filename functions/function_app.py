import html
import json
import logging
import os
from datetime import date

import azure.functions as func
import pyodbc
import requests


app = func.FunctionApp()


def get_db_connection():
    conn_str = os.environ["SqlOdbcConnectionString"]
    return pyodbc.connect(conn_str)


def normalize_report_date(value):
    if value is None:
        return None

    if isinstance(value, date):
        return value.isoformat()

    return str(value)[:10]


def already_sent(cursor, report_date: str) -> bool:
    cursor.execute(
        """
        SELECT COUNT(*)
        FROM dbo.daily_report_send_log
        WHERE report_date = CAST(? AS date)
          AND status = 'SENT'
        """,
        report_date,
    )
    return cursor.fetchone()[0] > 0


def load_daily_summary(cursor, report_date: str):
    cursor.execute(
        """
        SELECT
            equipment_id,
            window_end_time,
            avg_voltage_r,
            avg_voltage_s,
            avg_voltage_t,
            avg_current_r,
            avg_current_s,
            avg_current_t,
            avg_power_factor,
            avg_voltage_imbalance_rate,
            avg_current_imbalance_rate,
            event_count
        FROM dbo.poweroutput_1d
        WHERE CAST(DATEADD(day, -1, window_end_time) AS date) = CAST(? AS date)
        ORDER BY equipment_id
        """,
        report_date,
    )

    columns = [col[0] for col in cursor.description]
    return [dict(zip(columns, row)) for row in cursor.fetchall()]


def safe_float(value) -> float:
    try:
        if value is None:
            return 0.0
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def safe_int(value) -> int:
    try:
        if value is None:
            return 0
        return int(value)
    except (TypeError, ValueError):
        return 0


def get_expected_equipment_count() -> int:
    return int(os.environ.get("EXPECTED_EQUIPMENT_COUNT", "13"))


def get_expected_event_count_per_equipment() -> int:
    # 5초 단위 원천 데이터 기준: 24 * 60 * 60 / 5 = 17,280건
    return int(os.environ.get("EXPECTED_EVENT_COUNT_PER_EQUIPMENT", "17280"))


def get_equipment_status(row: dict) -> str:
    issue_count = 0

    if safe_float(row.get("avg_power_factor")) < 90:
        issue_count += 1
    if safe_float(row.get("avg_voltage_imbalance_rate")) >= 3:
        issue_count += 1
    if safe_float(row.get("avg_current_imbalance_rate")) >= 30:
        issue_count += 1

    if issue_count == 0:
        return "NORMAL"
    if issue_count == 1:
        return "WATCH"
    return "WARNING"


def build_summary(rows: list[dict]) -> dict:
    equipment_count = len(rows)

    avg_pf = (
        sum(safe_float(r.get("avg_power_factor")) for r in rows) / equipment_count
        if equipment_count > 0 else 0.0
    )
    avg_v_imb = (
        sum(safe_float(r.get("avg_voltage_imbalance_rate")) for r in rows) / equipment_count
        if equipment_count > 0 else 0.0
    )
    avg_c_imb = (
        sum(safe_float(r.get("avg_current_imbalance_rate")) for r in rows) / equipment_count
        if equipment_count > 0 else 0.0
    )

    low_pf_count = sum(
        1 for r in rows
        if r.get("avg_power_factor") is not None
        and safe_float(r.get("avg_power_factor")) < 90
    )

    high_v_imb_count = sum(
        1 for r in rows
        if r.get("avg_voltage_imbalance_rate") is not None
        and safe_float(r.get("avg_voltage_imbalance_rate")) >= 3
    )

    high_c_imb_count = sum(
        1 for r in rows
        if r.get("avg_current_imbalance_rate") is not None
        and safe_float(r.get("avg_current_imbalance_rate")) >= 30
    )

    total_event_count = sum(
        safe_int(r.get("event_count"))
        for r in rows
    )

    return {
        "equipment_count": equipment_count,
        "avg_power_factor": round(avg_pf, 2),
        "avg_voltage_imbalance_rate": round(avg_v_imb, 2),
        "avg_current_imbalance_rate": round(avg_c_imb, 2),
        "low_power_factor_count": low_pf_count,
        "high_voltage_imbalance_count": high_v_imb_count,
        "high_current_imbalance_count": high_c_imb_count,
        "total_event_count": total_event_count
    }


def build_abnormal_equipment(rows: list[dict]) -> list[dict]:
    abnormal = []

    for r in rows:
        issues = []

        pf = safe_float(r.get("avg_power_factor"))
        v_imb = safe_float(r.get("avg_voltage_imbalance_rate"))
        c_imb = safe_float(r.get("avg_current_imbalance_rate"))

        if r.get("avg_power_factor") is not None and pf < 90:
            issues.append(f"역률 저하({pf:.2f}%)")
        if r.get("avg_voltage_imbalance_rate") is not None and v_imb >= 3:
            issues.append(f"전압 불균형({v_imb:.2f}%)")
        if r.get("avg_current_imbalance_rate") is not None and c_imb >= 30:
            issues.append(f"전류 불균형({c_imb:.2f}%)")

        if issues:
            abnormal.append({
                "equipment_id": str(r.get("equipment_id")),
                "issues": issues,
                "event_count": safe_int(r.get("event_count")),
                "avg_power_factor": round(pf, 2),
                "avg_voltage_imbalance_rate": round(v_imb, 2),
                "avg_current_imbalance_rate": round(c_imb, 2),
                "status": get_equipment_status(r)
            })

    return sorted(abnormal, key=lambda x: x["event_count"], reverse=True)


def build_data_quality(summary: dict) -> dict:
    expected_equipment_count = get_expected_equipment_count()
    expected_event_count_per_equipment = get_expected_event_count_per_equipment()
    expected_total_event_count = expected_equipment_count * expected_event_count_per_equipment

    actual_equipment_count = summary["equipment_count"]
    actual_total_event_count = summary["total_event_count"]

    completeness_rate = (
        actual_total_event_count / expected_total_event_count * 100
        if expected_total_event_count > 0 else 0.0
    )

    return {
        "expected_equipment_count": expected_equipment_count,
        "actual_equipment_count": actual_equipment_count,
        "expected_event_count_per_equipment": expected_event_count_per_equipment,
        "expected_total_event_count": expected_total_event_count,
        "actual_total_event_count": actual_total_event_count,
        "completeness_rate": round(completeness_rate, 2),
    }


def get_daily_status(summary: dict, data_quality: dict) -> tuple[str, str]:
    abnormal_count = (
        summary["low_power_factor_count"]
        + summary["high_voltage_imbalance_count"]
        + summary["high_current_imbalance_count"]
    )

    if data_quality["actual_equipment_count"] < data_quality["expected_equipment_count"]:
        return (
            "WARNING",
            f"집계 설비 수가 {data_quality['actual_equipment_count']}개로 예상 설비 수 {data_quality['expected_equipment_count']}개보다 적습니다. 데이터 누락 여부 확인이 필요합니다."
        )

    if data_quality["completeness_rate"] < 95:
        return (
            "WATCH",
            f"수집 완전성이 {data_quality['completeness_rate']:.2f}%입니다. 일부 시간대 데이터 누락 여부 확인이 필요합니다."
        )

    if abnormal_count == 0:
        return (
            "NORMAL",
            "전체 설비에서 주요 전력 품질 이상 후보가 감지되지 않았습니다."
        )

    if abnormal_count <= 2:
        return (
            "WATCH",
            "일부 설비에서 이상 후보가 감지되었습니다. 추이 확인이 필요합니다."
        )

    return (
        "WARNING",
        "복수 설비에서 이상 후보가 감지되었습니다. 우선 점검 대상 확인이 필요합니다."
    )


def build_insights(summary: dict, abnormal_equipment: list[dict], data_quality: dict) -> list[str]:
    insights = []

    if data_quality["actual_equipment_count"] < data_quality["expected_equipment_count"]:
        insights.append(
            f"집계 설비 수가 {data_quality['actual_equipment_count']}개로 예상 설비 수 {data_quality['expected_equipment_count']}개보다 적습니다. 원천 데이터 누락 또는 집계 실패 여부를 확인해야 합니다."
        )

    if data_quality["completeness_rate"] < 95:
        insights.append(
            f"수집 완전성이 {data_quality['completeness_rate']:.2f}%로 낮습니다. 일부 시간대 또는 설비 데이터가 누락되었을 가능성이 있습니다."
        )

    if summary["low_power_factor_count"] > 0:
        insights.append(
            f"평균 역률 90% 미만 설비가 {summary['low_power_factor_count']}개 감지되었습니다. 무효전력 증가 및 요금 리스크를 확인해야 합니다."
        )

    if summary["high_voltage_imbalance_count"] > 0:
        insights.append(
            f"전압 불균형률 3% 이상 설비가 {summary['high_voltage_imbalance_count']}개 감지되었습니다. 전압 품질 및 설비 부하 상태 점검이 필요합니다."
        )

    if summary["high_current_imbalance_count"] > 0:
        insights.append(
            f"전류 불균형률 30% 이상 설비가 {summary['high_current_imbalance_count']}개 감지되었습니다. 상별 부하 편중 가능성이 있습니다."
        )

    if abnormal_equipment:
        top = abnormal_equipment[0]
        insights.append(
            f"우선 점검 대상은 {top['equipment_id']}입니다. 감지 항목: {', '.join(top['issues'])}."
        )

    if not insights:
        insights.append(
            "주요 전력 품질 지표와 데이터 수집 상태에서 특이사항은 감지되지 않았습니다."
        )

    return insights


def build_equipment_rows(rows: list[dict]) -> list[dict]:
    return [
        {
            "status": get_equipment_status(r),
            "equipment_id": str(r.get("equipment_id")),
            "avg_power_factor": round(safe_float(r.get("avg_power_factor")), 2),
            "avg_voltage_imbalance_rate": round(safe_float(r.get("avg_voltage_imbalance_rate")), 2),
            "avg_current_imbalance_rate": round(safe_float(r.get("avg_current_imbalance_rate")), 2),
            "event_count": safe_int(r.get("event_count"))
        }
        for r in rows
    ]


def build_markdown_report(report_date: str, rows: list[dict]) -> str:
    summary = build_summary(rows)
    abnormal_equipment = build_abnormal_equipment(rows)
    data_quality = build_data_quality(summary)
    daily_status, daily_status_message = get_daily_status(summary, data_quality)
    insights = build_insights(summary, abnormal_equipment, data_quality)

    lines = []

    lines.append(f"## 일일 전력 관제 리포트 - {report_date}")
    lines.append("")
    lines.append("### 오늘의 종합 상태")
    lines.append(f"- **{daily_status}** - {daily_status_message}")
    lines.append("")
    lines.append("### 전체 요약")
    lines.append(f"- 집계 설비 수: **{summary['equipment_count']}개**")
    lines.append(f"- 평균 역률: **{summary['avg_power_factor']:.2f}%**")
    lines.append(f"- 평균 전압 불균형률: **{summary['avg_voltage_imbalance_rate']:.2f}%**")
    lines.append(f"- 평균 전류 불균형률: **{summary['avg_current_imbalance_rate']:.2f}%**")
    lines.append(f"- 전체 이벤트 수: **{summary['total_event_count']:,}건**")
    lines.append("")
    lines.append("### 이상 후보 요약")
    lines.append(f"- 평균 역률 90% 미만 설비: **{summary['low_power_factor_count']}개**")
    lines.append(f"- 전압 불균형률 3% 이상 설비: **{summary['high_voltage_imbalance_count']}개**")
    lines.append(f"- 전류 불균형률 30% 이상 설비: **{summary['high_current_imbalance_count']}개**")
    lines.append("")
    lines.append("### 주요 점검 대상 설비")
    lines.append("| 설비 | 감지 항목 | 이벤트수 |")
    lines.append("|---|---|---:|")

    if abnormal_equipment:
        for a in abnormal_equipment[:5]:
            lines.append(
                f"| {a['equipment_id']} "
                f"| {', '.join(a['issues'])} "
                f"| {a['event_count']} |"
            )
    else:
        lines.append("| - | 주요 이상 후보 설비 없음 | - |")

    lines.append("")
    lines.append("### 자동 진단 코멘트")

    for insight in insights:
        lines.append(f"- {insight}")

    lines.append("")
    lines.append("### 데이터 품질 체크")
    lines.append(f"- 예상 설비 수: **{data_quality['expected_equipment_count']}개**")
    lines.append(f"- 실제 집계 설비 수: **{data_quality['actual_equipment_count']}개**")
    lines.append(f"- 예상 이벤트 수: **{data_quality['expected_total_event_count']:,}건**")
    lines.append(f"- 실제 이벤트 수: **{data_quality['actual_total_event_count']:,}건**")
    lines.append(f"- 수집 완전성: **{data_quality['completeness_rate']:.2f}%**")
    lines.append("")
    lines.append("### 설비별 요약")
    lines.append("| 상태 | 설비 | 평균역률 | 전압불균형률 | 전류불균형률 | 이벤트수 |")
    lines.append("|---|---|---:|---:|---:|---:|")

    for r in rows:
        lines.append(
            f"| {get_equipment_status(r)} "
            f"| {r.get('equipment_id')} "
            f"| {safe_float(r.get('avg_power_factor')):.2f}% "
            f"| {safe_float(r.get('avg_voltage_imbalance_rate')):.2f}% "
            f"| {safe_float(r.get('avg_current_imbalance_rate')):.2f}% "
            f"| {safe_int(r.get('event_count'))} |"
        )

    return "\n".join(lines)


def build_html_report(report_date: str, rows: list[dict]) -> str:
    summary = build_summary(rows)
    abnormal_equipment = build_abnormal_equipment(rows)
    data_quality = build_data_quality(summary)
    daily_status, daily_status_message = get_daily_status(summary, data_quality)
    insights = build_insights(summary, abnormal_equipment, data_quality)

    status_style = {
        "NORMAL": "color:#107c10;font-weight:bold;",
        "WATCH": "color:#986f0b;font-weight:bold;",
        "WARNING": "color:#c50f1f;font-weight:bold;",
    }.get(daily_status, "font-weight:bold;")

    insight_items = ""

    for text in insights:
        insight_items += f"""
        <li>{html.escape(text)}</li>
        """

    abnormal_rows = ""

    if abnormal_equipment:
        for a in abnormal_equipment[:5]:
            abnormal_rows += f"""
            <tr>
                <td>{html.escape(a['equipment_id'])}</td>
                <td>{html.escape(', '.join(a['issues']))}</td>
                <td style="text-align:right;">{a['event_count']}</td>
            </tr>
            """
    else:
        abnormal_rows = """
        <tr>
            <td colspan="3" style="text-align:center;">주요 이상 후보 설비 없음</td>
        </tr>
        """

    table_rows = ""

    for r in rows:
        status = get_equipment_status(r)

        table_rows += f"""
        <tr>
            <td>{status}</td>
            <td>{html.escape(str(r.get('equipment_id')))}</td>
            <td style="text-align:right;">{safe_float(r.get('avg_power_factor')):.2f}%</td>
            <td style="text-align:right;">{safe_float(r.get('avg_voltage_imbalance_rate')):.2f}%</td>
            <td style="text-align:right;">{safe_float(r.get('avg_current_imbalance_rate')):.2f}%</td>
            <td style="text-align:right;">{safe_int(r.get('event_count'))}</td>
        </tr>
        """

    return f"""
    <html>
    <body style="font-family:Arial, sans-serif; line-height:1.45;">
        <h2>일일 전력 관제 리포트 - {html.escape(report_date)}</h2>

        <h3>오늘의 종합 상태</h3>
        <p>
            <span style="{status_style}">{daily_status}</span> - {html.escape(daily_status_message)}
        </p>

        <h3>전체 요약</h3>
        <ul>
            <li>집계 설비 수: <b>{summary['equipment_count']}개</b></li>
            <li>평균 역률: <b>{summary['avg_power_factor']:.2f}%</b></li>
            <li>평균 전압 불균형률: <b>{summary['avg_voltage_imbalance_rate']:.2f}%</b></li>
            <li>평균 전류 불균형률: <b>{summary['avg_current_imbalance_rate']:.2f}%</b></li>
            <li>전체 이벤트 수: <b>{summary['total_event_count']:,}건</b></li>
        </ul>

        <h3>이상 후보 요약</h3>
        <ul>
            <li>평균 역률 90% 미만 설비: <b>{summary['low_power_factor_count']}개</b></li>
            <li>전압 불균형률 3% 이상 설비: <b>{summary['high_voltage_imbalance_count']}개</b></li>
            <li>전류 불균형률 30% 이상 설비: <b>{summary['high_current_imbalance_count']}개</b></li>
        </ul>

        <h3>주요 점검 대상 설비</h3>
        <table border="1" cellpadding="6" cellspacing="0" style="border-collapse:collapse;">
            <thead>
                <tr>
                    <th>설비</th>
                    <th>감지 항목</th>
                    <th>이벤트수</th>
                </tr>
            </thead>
            <tbody>
                {abnormal_rows}
            </tbody>
        </table>

        <h3>자동 진단 코멘트</h3>
        <ul>
            {insight_items}
        </ul>

        <h3>데이터 품질 체크</h3>
        <ul>
            <li>예상 설비 수: <b>{data_quality['expected_equipment_count']}개</b></li>
            <li>실제 집계 설비 수: <b>{data_quality['actual_equipment_count']}개</b></li>
            <li>예상 이벤트 수: <b>{data_quality['expected_total_event_count']:,}건</b></li>
            <li>실제 이벤트 수: <b>{data_quality['actual_total_event_count']:,}건</b></li>
            <li>수집 완전성: <b>{data_quality['completeness_rate']:.2f}%</b></li>
        </ul>

        <h3>설비별 요약</h3>
        <table border="1" cellpadding="6" cellspacing="0" style="border-collapse:collapse;">
            <thead>
                <tr>
                    <th>상태</th>
                    <th>설비</th>
                    <th>평균역률</th>
                    <th>전압불균형률</th>
                    <th>전류불균형률</th>
                    <th>이벤트수</th>
                </tr>
            </thead>
            <tbody>
                {table_rows}
            </tbody>
        </table>
    </body>
    </html>
    """
def send_to_workflow(payload: dict):
    webhook_url = os.environ["TEAMS_WEBHOOK_URL"]

    response = requests.post(webhook_url, json=payload, timeout=15)
    response.raise_for_status()


def upsert_send_log(cursor, report_date: str, status: str, message: str):
    cursor.execute(
        """
        MERGE dbo.daily_report_send_log AS target
        USING (
            SELECT
                CAST(? AS date) AS report_date,
                CAST(? AS nvarchar(20)) AS status,
                CAST(? AS nvarchar(max)) AS message
        ) AS source
        ON target.report_date = source.report_date

        WHEN MATCHED THEN
            UPDATE SET
                sent_at = SYSDATETIME(),
                status = source.status,
                message = source.message

        WHEN NOT MATCHED THEN
            INSERT (
                report_date,
                sent_at,
                status,
                message
            )
            VALUES (
                source.report_date,
                SYSDATETIME(),
                source.status,
                source.message
            );
        """,
        report_date,
        status,
        message,
    )


@app.function_name(name="DailyReportSqlTrigger")
@app.sql_trigger(
    arg_name="changes",
    table_name="dbo.reportstatus",
    connection_string_setting="SqlTriggerConnectionString"
)
def daily_report_sql_trigger(changes: str) -> None:
    logging.info("SQL changes received: %s", changes)

    expected_count = int(os.environ.get("EXPECTED_EQUIPMENT_COUNT", "13"))

    try:
        change_items = json.loads(changes)
    except Exception:
        logging.exception("Failed to parse SQL trigger payload.")
        return

    conn = get_db_connection()
    cursor = conn.cursor()

    report_date = None

    try:
        for change in change_items:
            operation = change.get("Operation")
            item = change.get("Item", {})

            status = item.get("status")
            report_date = normalize_report_date(item.get("report_date"))

            logging.info(
                "Detected change. operation=%s, report_date=%s, status=%s",
                operation,
                report_date,
                status,
            )
            logging.info("DEBUG CHECKPOINT 1 - before operation filter")

            if operation not in ("Insert", 0):
                logging.info("DEBUG SKIP - operation is not insert. operation=%s", operation)
                continue

            logging.info("DEBUG CHECKPOINT 2 - passed operation filter")

            if status != "READY":
                logging.info("DEBUG SKIP - status is not READY. status=%s", status)
                continue

            logging.info("DEBUG CHECKPOINT 3 - passed status filter")

            if report_date is None:
                logging.warning("report_date is missing. Skip.")
                continue

            if already_sent(cursor, report_date):
                logging.info("Report already sent. report_date=%s", report_date)
                continue

            rows = load_daily_summary(cursor, report_date)

            if len(rows) < expected_count:
                message = (
                    f"Daily summary is not complete. "
                    f"report_date={report_date}, "
                    f"actual_count={len(rows)}, "
                    f"expected_count={expected_count}"
                )
                logging.warning(message)
                upsert_send_log(cursor, report_date, "WAITING", message)
                conn.commit()
                continue

            markdown_report = build_markdown_report(report_date, rows)
            html_report = build_html_report(report_date, rows)
            summary = build_summary(rows)
            equipment_rows = build_equipment_rows(rows)

            payload = {
                "report_date": report_date,
                "title": f"일일 전력 관제 리포트 - {report_date}",
                "text": markdown_report,
                "html": html_report,
                "summary": summary,
                "equipment_rows": equipment_rows
            }

            send_to_workflow(payload)

            upsert_send_log(
                cursor,
                report_date,
                "SENT",
                "Daily report workflow sent successfully."
            )
            conn.commit()

            logging.info("Daily report sent successfully. report_date=%s", report_date)

    except Exception as e:
        logging.exception("Daily report function failed.")

        try:
            if report_date:
                upsert_send_log(cursor, report_date, "FAILED", str(e))
                conn.commit()
        except Exception:
            logging.exception("Failed to write failure log.")

    finally:
        cursor.close()
        conn.close()
