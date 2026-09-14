import os
import json
import logging
import requests
import azure.functions as func

from report_builder import build_daily_report


app = func.FunctionApp()


@app.timer_trigger(
    schedule="0 0 0 * * *",
    arg_name="myTimer",
    run_on_startup=False,
    use_monitor=True
)
def daily_power_report(myTimer: func.TimerRequest) -> None:
    """
    매일 00:00 UTC 실행.
    한국시간 기준 매일 09:00 실행.
    """
    logging.info("Daily power report function started.")

    if myTimer.past_due:
        logging.warning("The timer is past due.")

    try:
        report = build_daily_report()

        logic_app_url = os.environ["LOGIC_APP_EMAIL_URL"]
        to_email = os.environ["REPORT_TO_EMAIL"]
        cc_email = os.environ.get("REPORT_CC_EMAIL", "")

        payload = {
            "to": to_email,
            "cc": cc_email,
            "subject": report["subject"],
            "html": report["html"],
            "summary": report["summary"]
        }

        response = requests.post(
            logic_app_url,
            headers={"Content-Type": "application/json"},
            data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
            timeout=30
        )

        response.raise_for_status()

        logging.info("Daily report sent successfully.")
        logging.info("Report summary: %s", report["summary"])

    except Exception as e:
        logging.exception("Failed to send daily report: %s", str(e))
        raise