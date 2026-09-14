# src/utils.py

import pandas as pd


def filter_until_today_midnight(
    forecast_df: pd.DataFrame,
    base_time: pd.Timestamp,
) -> pd.DataFrame:
    """
    base_time 기준 당일 24시까지의 예측값만 남김.
    예: base_time = 2025-05-01 13:00
    target upper bound = 2025-05-02 00:00
    """

    target_end_time = (
        pd.Timestamp(base_time)
        .normalize()
        + pd.Timedelta(days=1)
    )

    return forecast_df[
        forecast_df["ds"] <= target_end_time
    ].copy()


def normalize_forecast_output(
    forecast_df: pd.DataFrame,
    model_name: str,
    base_time: pd.Timestamp,
) -> pd.DataFrame:
    """
    NeuralForecast 예측 결과를 DB 저장용 포맷으로 변환.
    """

    possible_yhat_cols = [
        model_name,
        f"{model_name}-median",
        "yhat",
    ]

    yhat_col = None
    for col in possible_yhat_cols:
        if col in forecast_df.columns:
            yhat_col = col
            break

    if yhat_col is None:
        raise ValueError(
            f"{model_name} 예측 결과에서 yhat 컬럼을 찾을 수 없습니다. "
            f"현재 컬럼: {list(forecast_df.columns)}"
        )

    result_df = forecast_df[["unique_id", "ds", yhat_col]].copy()

    result_df = result_df.rename(
        columns={
            "unique_id": "equipment_id",
            "ds": "target_time",
            yhat_col: "yhat",
        }
    )

    result_df["model_name"] = model_name
    result_df["base_time"] = base_time
    result_df["created_at"] = pd.Timestamp.utcnow().tz_localize(None)

    result_df = result_df[
        [
            "base_time",
            "target_time",
            "equipment_id",
            "model_name",
            "yhat",
            "created_at",
        ]
    ]

    return result_df