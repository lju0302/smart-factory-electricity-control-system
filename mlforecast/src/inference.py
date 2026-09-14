# ?듭떖 異붾줎 ?ㅽ뻾

# src/inference.py

import logging
import pandas as pd

from src.config import get_settings
from src.db import (
    create_sql_engine,
    get_base_time,
    load_inference_data,
    save_forecast_result,
)
from src.model_loader import load_models
from src.utils import (
    filter_until_today_midnight,
    normalize_forecast_output,
)


def run_forecast_once() -> None:
    logging.info("Forecast job started.")

    settings = get_settings()
    engine = create_sql_engine(settings)

    base_time = get_base_time(
        engine=engine,
        input_table=settings.input_table,
    )

    logging.info("Base time: %s", base_time)

    input_df = load_inference_data(
        engine=engine,
        input_table=settings.input_table,
        base_time=base_time,
    )

    logging.info("Loaded inference data. rows=%s", len(input_df))

    models = load_models(
        nhits_dir=settings.model_dir_nhits,
        tft_dir=settings.model_dir_tft,
    )

    all_results = []

    for model_name, model in models.items():
        logging.info("Running forecast. model=%s", model_name)

        forecast_df = model.predict(df=input_df)

        forecast_df = filter_until_today_midnight(
            forecast_df=forecast_df,
            base_time=base_time,
        )

        result_df = normalize_forecast_output(
            forecast_df=forecast_df,
            model_name=model_name,
            base_time=base_time,
        )

        all_results.append(result_df)

        logging.info(
            "Forecast completed. model=%s, rows=%s",
            model_name,
            len(result_df),
        )

    final_result_df = pd.concat(all_results, ignore_index=True)

    save_forecast_result(
        engine=engine,
        output_table=settings.output_table,
        result_df=final_result_df,
    )

    logging.info(
        "Forecast job finished. saved_rows=%s",
        len(final_result_df),
    )


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    run_forecast_once()


