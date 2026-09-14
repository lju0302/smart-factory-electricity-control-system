import pandas as pd


class AnomalyInjector:
    def __init__(self):
        self.injected_count = 0

    def inject_demo_anomaly(self, df: pd.DataFrame) -> pd.DataFrame:
        if df.empty:
            return df

        result = df.copy()

        # 데모용으로 특정 구간 일부에만 이상을 주입한다.
        # 너무 자주 넣으면 모든 데이터가 이상처럼 보이므로 50번째 timestamp 그룹마다 한 번씩 주입한다.
        unique_timestamps = sorted(result["timestamp"].unique())

        if len(unique_timestamps) == 0:
            return result

        target_timestamp = unique_timestamps[len(unique_timestamps) // 2]

        mask = result["timestamp"] == target_timestamp

        # 과부하형 이상: activePower와 current를 동시에 증가시킨다.
        result.loc[mask, "activePower"] = result.loc[mask, "activePower"] * 1.6
        result.loc[mask, "currentR"] = result.loc[mask, "currentR"] * 1.4
        result.loc[mask, "currentS"] = result.loc[mask, "currentS"] * 1.4
        result.loc[mask, "currentT"] = result.loc[mask, "currentT"] * 1.4

        # 역률 저하형 이상: powerFactor를 낮춘다.
        result.loc[mask, "powerFactorR"] = result.loc[mask, "powerFactorR"] * 0.75
        result.loc[mask, "powerFactorS"] = result.loc[mask, "powerFactorS"] * 0.75
        result.loc[mask, "powerFactorT"] = result.loc[mask, "powerFactorT"] * 0.75

        result.loc[mask, "synthetic_anomaly"] = True
        result.loc[mask, "synthetic_anomaly_type"] = "overload_low_power_factor"

        result.loc[~mask, "synthetic_anomaly"] = False
        result.loc[~mask, "synthetic_anomaly_type"] = "normal"

        self.injected_count += int(mask.sum())

        return result