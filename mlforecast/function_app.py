# function_app.py

import logging
import azure.functions as func

from src.inference import run_forecast_once


app = func.FunctionApp()


@app.timer_trigger(
    schedule="0 0 */1 * * *",
    arg_name="myTimer",
    run_on_startup=True,
    use_monitor=True,
)
def forecast_timer(myTimer: func.TimerRequest) -> None:
    if myTimer.past_due:
        logging.warning("Timer trigger is past due.")

    logging.info("Timer trigger started.")

    try:
        run_forecast_once()
    except Exception:
        logging.exception("Forecast job failed.")
        raise

    logging.info("Timer trigger finished.")