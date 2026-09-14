import os
import pyodbc
import pandas as pd
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo


KST = ZoneInfo("Asia/Seoul")


def get_sql_connection():
    server = os.environ["SQL_SERVER"]
    database = os.environ["SQL_DATABASE"]
    username = os.environ["SQL_USERNAME"]
    password = os.environ["SQL_PASSWORD"]

    conn_str = (
        "DRIVER={ODBC Driver 18 for SQL Server};"
        f"SERVER={server};"
        f"DATABASE={database};"
        f"UID={username};"
        f"PWD={password};"
        "Encrypt=yes;"
        "TrustServerCertificate=no;"
        "Connection Timeout=30;"
    )

    return pyodbc.connect(conn_str)


def get_yesterday_range_kst():
    now_kst = datetime.now(KST)
    today_kst = now_kst.date()

    start_kst = datetime.combine(today_kst - timedelta(days=1), datetime.min.time(), tzinfo=KST)
    end_kst = datetime.combine(today_kst, datetime.min.time(), tzinfo=KST)

    return start_kst, end_kst


def to_utc_naive(dt_kst: datetime):
    """
    DB 시간이 UTC DATETIME2로 저장되어 있다고 가정.
    DATETIME2에는 timezone이 없으므로 UTC naive datetime으로 넘김.
    """
    return dt_kst.astimezone(timezone.utc).replace(tzinfo=None)


def load_daily_kpi(conn, start_utc, end_utc):
    query = """
    SELECT
        equipment_id,

        COUNT(*) AS row_count,

        AVG(avg_voltage_r) AS daily_avg_voltage_r,
        AVG(avg_voltage_s) AS daily_avg_voltage_s,
        AVG(avg_voltage_t) AS daily_avg_voltage_t,

        AVG(avg_current_r) AS daily_avg_current_r,
        AVG(avg_current_s) AS daily_avg_current_s,
        AVG(avg_current_t) AS daily_avg_current_t,

        AVG(avg_power_factor) AS daily_avg_power_factor,

        AVG(avg_active_power) AS daily_avg_active_power,
        MAX(avg_active_power) AS daily_peak_active_power,
        MIN(avg_active_power) AS daily_min_active_power

    FROM dbo.power_1min_agg
    WHERE window_ent_time >= ?
      AND window_ent_time < ?
    GROUP BY equipment_id
    ORDER BY equipment_id;
    """

    return pd.read_sql(query, conn, params=[start_utc, end_utc])


def load_alert_summary(conn, start_utc, end_utc):
    query = """
    SELECT
        equipment_id,
        alert_type,
        severity,
        COUNT(*) AS alert_count,
        MIN(detected_at) AS first_detected_at,
        MAX(detected_at) AS last_detected_at
    FROM dbo.power_alert_events
    WHERE detected_at >= ?
      AND detected_at < ?
    GROUP BY equipment_id, alert_type, severity
    ORDER BY alert_count DESC, equipment_id;
    """

    return pd.read_sql(query, conn, params=[start_utc, end_utc])


def load_top_alert_equipment(conn, start_utc, end_utc):
    query = """
    SELECT TOP 5
        equipment_id,
        COUNT(*) AS total_alert_count
    FROM dbo.power_alert_events
    WHERE detected_at >= ?
      AND detected_at < ?
    GROUP BY equipment_id
    ORDER BY total_alert_count DESC;
    """

    return pd.read_sql(query, conn, params=[start_utc, end_utc])


def fmt_number(value, digits=2):
    if pd.isna(value):
        return "-"
    return f"{value:,.{digits}f}"


def dataframe_to_html_table(df: pd.DataFrame, max_rows=20):
    if df.empty:
        return "<p>해당 기간 데이터가 없습니다.</p>"

    return df.head(max_rows).to_html(
        index=False,
        border=0,
        classes="report-table",
        justify="center"
    )


def build_daily_report_html(kpi_df, alert_df, top_alert_df, start_kst, end_kst):
    report_date = start_kst.strftime("%Y-%m-%d")

    total_equipment = int(kpi_df["equipment_id"].nunique()) if not kpi_df.empty else 0
    total_alerts = int(alert_df["alert_count"].sum()) if not alert_df.empty else 0
    alert_equipment = int(alert_df["equipment_id"].nunique()) if not alert_df.empty else 0

    if not kpi_df.empty and "daily_peak_active_power" in kpi_df.columns:
        peak_row = kpi_df.sort_values("daily_peak_active_power", ascending=False).iloc[0]
        peak_equipment = peak_row["equipment_id"]
        peak_power = fmt_number(peak_row["daily_peak_active_power"])
    else:
        peak_equipment = "-"
        peak_power = "-"

    if not alert_df.empty:
        top_alert_type_row = (
            alert_df.groupby("alert_type", as_index=False)["alert_count"]
            .sum()
            .sort_values("alert_count", ascending=False)
            .iloc[0]
        )
        main_alert_type = top_alert_type_row["alert_type"]
        main_alert_count = int(top_alert_type_row["alert_count"])
    else:
        main_alert_type = "-"
        main_alert_count = 0

    kpi_view = kpi_df.copy()
    if not kpi_view.empty:
        kpi_view = kpi_view.rename(columns={
            "equipment_id": "설비",
            "row_count": "집계건수",
            "daily_avg_voltage_r": "R상 평균전압",
            "daily_avg_voltage_s": "S상 평균전압",
            "daily_avg_voltage_t": "T상 평균전압",
            "daily_avg_current_r": "R상 평균전류",
            "daily_avg_current_s": "S상 평균전류",
            "daily_avg_current_t": "T상 평균전류",
            "daily_avg_power_factor": "평균역률",
            "daily_avg_active_power": "평균유효전력",
            "daily_peak_active_power": "최대유효전력",
            "daily_min_active_power": "최소유효전력"
        })

    alert_view = alert_df.copy()
    if not alert_view.empty:
        alert_view = alert_view.rename(columns={
            "equipment_id": "설비",
            "alert_type": "이상유형",
            "severity": "심각도",
            "alert_count": "발생건수",
            "first_detected_at": "최초발생시각",
            "last_detected_at": "최종발생시각"
        })

    top_alert_view = top_alert_df.copy()
    if not top_alert_view.empty:
        top_alert_view = top_alert_view.rename(columns={
            "equipment_id": "설비",
            "total_alert_count": "총 이상건수"
        })

    html = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="utf-8">
        <style>
            body {{
                font-family: Arial, 'Malgun Gothic', sans-serif;
                color: #222;
                line-height: 1.5;
            }}
            .container {{
                max-width: 900px;
                margin: 0 auto;
                padding: 20px;
            }}
            .title {{
                font-size: 24px;
                font-weight: bold;
                margin-bottom: 4px;
            }}
            .subtitle {{
                color: #666;
                margin-bottom: 24px;
            }}
            .card {{
                border: 1px solid #ddd;
                border-radius: 10px;
                padding: 16px;
                margin-bottom: 16px;
                background-color: #fafafa;
            }}
            .metric-grid {{
                display: grid;
                grid-template-columns: repeat(2, minmax(0, 1fr));
                gap: 12px;
            }}
            .metric {{
                background: white;
                border: 1px solid #e5e5e5;
                border-radius: 8px;
                padding: 12px;
            }}
            .metric-label {{
                color: #666;
                font-size: 13px;
            }}
            .metric-value {{
                font-size: 20px;
                font-weight: bold;
                margin-top: 4px;
            }}
            .section-title {{
                font-size: 18px;
                font-weight: bold;
                margin-top: 28px;
                margin-bottom: 10px;
            }}
            .report-table {{
                border-collapse: collapse;
                width: 100%;
                font-size: 13px;
            }}
            .report-table th {{
                background-color: #f0f0f0;
                border: 1px solid #ddd;
                padding: 8px;
                text-align: center;
            }}
            .report-table td {{
                border: 1px solid #ddd;
                padding: 8px;
                text-align: center;
            }}
            .comment {{
                background-color: #fff8e1;
                border-left: 5px solid #f6c343;
                padding: 12px;
                margin-top: 12px;
            }}
        </style>
    </head>
    <body>
    <div class="container">
        <div class="title">일일 설비 전력 관제 리포트</div>
        <div class="subtitle">
            기준일: {report_date} / 집계 구간: {start_kst.strftime('%Y-%m-%d %H:%M')} ~ {end_kst.strftime('%Y-%m-%d %H:%M')} KST
        </div>

        <div class="card">
            <div class="section-title">1. 전체 요약</div>
            <div class="metric-grid">
                <div class="metric">
                    <div class="metric-label">모니터링 설비 수</div>
                    <div class="metric-value">{total_equipment}개</div>
                </div>
                <div class="metric">
                    <div class="metric-label">이상 발생 설비 수</div>
                    <div class="metric-value">{alert_equipment}개</div>
                </div>
                <div class="metric">
                    <div class="metric-label">전체 이상 이벤트</div>
                    <div class="metric-value">{total_alerts}건</div>
                </div>
                <div class="metric">
                    <div class="metric-label">최대 피크 전력 설비</div>
                    <div class="metric-value">{peak_equipment} / {peak_power}</div>
                </div>
            </div>

            <div class="comment">
                주요 이상 유형은 <b>{main_alert_type}</b>이며, 총 <b>{main_alert_count}</b>건 발생했습니다.
            </div>
        </div>

        <div class="section-title">2. 이상 발생 TOP 5 설비</div>
        {dataframe_to_html_table(top_alert_view, max_rows=5)}

        <div class="section-title">3. 이상 이벤트 요약</div>
        {dataframe_to_html_table(alert_view, max_rows=30)}

        <div class="section-title">4. 설비별 일일 KPI</div>
        {dataframe_to_html_table(kpi_view, max_rows=30)}

        <div class="section-title">5. 운영 코멘트</div>
        <div class="comment">
            이상 이벤트가 반복 발생한 설비는 5분/15분 집계 기준으로 재확인하고,
            역률 저하, 전압 불균형, 전류 불균형 항목별로 설비 점검 우선순위를 부여하는 것을 권장합니다.
        </div>
    </div>
    </body>
    </html>
    """

    return html


def build_daily_report():
    start_kst, end_kst = get_yesterday_range_kst()
    start_utc = to_utc_naive(start_kst)
    end_utc = to_utc_naive(end_kst)

    with get_sql_connection() as conn:
        kpi_df = load_daily_kpi(conn, start_utc, end_utc)
        alert_df = load_alert_summary(conn, start_utc, end_utc)
        top_alert_df = load_top_alert_equipment(conn, start_utc, end_utc)

    html = build_daily_report_html(
        kpi_df=kpi_df,
        alert_df=alert_df,
        top_alert_df=top_alert_df,
        start_kst=start_kst,
        end_kst=end_kst
    )

    subject = f"[일일 설비 전력 관제 리포트] {start_kst.strftime('%Y-%m-%d')}"

    summary = {
        "report_date": start_kst.strftime("%Y-%m-%d"),
        "equipment_count": int(kpi_df["equipment_id"].nunique()) if not kpi_df.empty else 0,
        "total_alert_count": int(alert_df["alert_count"].sum()) if not alert_df.empty else 0,
        "alert_equipment_count": int(alert_df["equipment_id"].nunique()) if not alert_df.empty else 0,
    }

    return {
        "subject": subject,
        "html": html,
        "summary": summary
    }