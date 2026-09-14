import json
import os
from datetime import datetime, timezone
from pathlib import Path

import joblib
import numpy as np
import pandas as pd


SUPPORTED_LEVELS = ["1m", "15m", "1h", "1d"]

REQUIRED_INPUT_COLUMNS = [
    "equipment_id",
    "window_end_time",
    "aggregation_level",
    "avg_voltage_r",
    "avg_voltage_s",
    "avg_voltage_t",
    "avg_current_r",
    "avg_current_s",
    "avg_current_t",
    "avg_power_factor",
    "avg_voltage_imbalance_rate",
    "avg_current_imbalance_rate",
    "event_count",
    "rolling_15m_peak_kW",
    "carbon_emission_kg",
    "kepco_10m_v_imb",
    "kepco_10m_c_imb",
    "kepco_30m_pf",
    "hour",
    "dayofweek",
    "is_weekend",
]

NUMERIC_INPUT_COLUMNS = [
    "avg_voltage_r",
    "avg_voltage_s",
    "avg_voltage_t",
    "avg_current_r",
    "avg_current_s",
    "avg_current_t",
    "avg_power_factor",
    "avg_voltage_imbalance_rate",
    "avg_current_imbalance_rate",
    "event_count",
    "rolling_15m_peak_kW",
    "carbon_emission_kg",
    "kepco_10m_v_imb",
    "kepco_10m_c_imb",
    "kepco_30m_pf",
    "hour",
    "dayofweek",
    "is_weekend",
    "completeness_ratio",
    "estimated_kW",
    "rolling_15m_avg_kW",
]

RULE_DIRECTIONS = {
    "avg_current_imbalance_rate": "high",
    "avg_voltage_imbalance_rate": "high",
    "rolling_15m_peak_kW": "high",
    "carbon_emission_kg": "high",
    "avg_power_factor": "low",
    "kepco_30m_pf": "low",
}

ACTION_MAP = {
    "avg_current_imbalance_rate_high": "전류 불균형 및 부하 편차 점검",
    "avg_voltage_imbalance_rate_high": "전압 불평형 및 전원 품질 점검",
    "avg_power_factor_low": "역률 저하 및 무효전력 보상 상태 점검",
    "kepco_30m_pf_low": "누적 역률 저하 원인 점검",
    "rolling_15m_peak_kW_high": "피크 부하 및 설비 동시 가동 여부 점검",
    "carbon_emission_kg_high": "고부하 운전 및 에너지 사용량 점검",
}

EXPECTED_EVENT_COUNTS = {"1m": 12, "15m": 180, "1h": 720, "1d": 17280}

MODELS = {}
SCALERS = {}
RULE_THRESHOLDS = {}
FEATURE_CONFIG = {}
FINAL_SCORE_LOGIC = {}
OUTPUT_SCHEMA = {}
BASE_DIR = None


def _json_load(path):
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def _resolve_model_dir():
    azure_model_dir = os.environ.get("AZUREML_MODEL_DIR")
    candidates = []
    if azure_model_dir:
        candidates.append(Path(azure_model_dir))
        candidates.append(Path(azure_model_dir) / "ml_package")
    here = Path(__file__).resolve().parent
    candidates.extend([here, here.parent / "ml_package"])
    for candidate in candidates:
        if (candidate / "models").exists() and (candidate / "config").exists():
            return candidate
    return here


def init():
    global MODELS, SCALERS, RULE_THRESHOLDS, FEATURE_CONFIG, FINAL_SCORE_LOGIC, OUTPUT_SCHEMA, BASE_DIR
    BASE_DIR = _resolve_model_dir()
    config_dir = BASE_DIR / "config"
    model_dir = BASE_DIR / "models"

    RULE_THRESHOLDS = _json_load(config_dir / "rule_thresholds_train_through_march.json")
    FEATURE_CONFIG = _json_load(config_dir / "anomaly_feature_columns.json")
    FINAL_SCORE_LOGIC = _json_load(config_dir / "final_score_logic.json")
    OUTPUT_SCHEMA = _json_load(config_dir / "anomaly_output_schema.json")

    MODELS = {}
    SCALERS = {}
    for level in SUPPORTED_LEVELS:
        MODELS[level] = joblib.load(model_dir / f"isolation_forest_{level}.joblib")
        SCALERS[level] = joblib.load(model_dir / f"standard_scaler_{level}.joblib")


def _parse_raw_data(raw_data):
    if isinstance(raw_data, str):
        payload = json.loads(raw_data)
    else:
        payload = raw_data
    if isinstance(payload, dict) and "data" in payload:
        rows = payload["data"]
    else:
        rows = payload
    if isinstance(rows, dict):
        rows = [rows]
    if not isinstance(rows, list) or not rows:
        raise ValueError("Input must be a JSON object, a row list, or {'data': [rows]}.")
    if not all(isinstance(row, dict) for row in rows):
        raise ValueError("Each input row must be a JSON object.")
    return rows


def _to_float(value, default=0.0):
    try:
        if value is None:
            return default
        value = float(value)
        if not np.isfinite(value):
            return default
        return value
    except Exception:
        return default


def _prepare_row(row):
    missing = [col for col in REQUIRED_INPUT_COLUMNS if col not in row]
    if missing:
        raise ValueError(f"Missing required columns: {missing}")
    level = str(row.get("aggregation_level"))
    if level not in SUPPORTED_LEVELS:
        raise ValueError(f"Unsupported aggregation_level '{level}'. Supported: {SUPPORTED_LEVELS}")

    out = dict(row)
    out["equipment_id"] = str(out["equipment_id"])
    out["aggregation_level"] = level
    out["window_end_time"] = str(out["window_end_time"])

    for col in NUMERIC_INPUT_COLUMNS:
        if col in out:
            out[col] = _to_float(out[col])

    voltage_avg = np.mean([out["avg_voltage_r"], out["avg_voltage_s"], out["avg_voltage_t"]])
    current_avg = np.mean([out["avg_current_r"], out["avg_current_s"], out["avg_current_t"]])
    pf_decimal = out["avg_power_factor"] / 100 if out["avg_power_factor"] > 1 else out["avg_power_factor"]
    if "estimated_kW" not in out or not np.isfinite(_to_float(out.get("estimated_kW"))):
        out["estimated_kW"] = float(np.sqrt(3) * voltage_avg * current_avg * pf_decimal / 1000)
    if "rolling_15m_avg_kW" not in out or not np.isfinite(_to_float(out.get("rolling_15m_avg_kW"))):
        out["rolling_15m_avg_kW"] = float(out["estimated_kW"])
    if "completeness_ratio" not in out:
        expected = EXPECTED_EVENT_COUNTS[level]
        out["completeness_ratio"] = float(out["event_count"] / expected) if expected else 1.0
    out["completeness_ratio"] = float(np.clip(out["completeness_ratio"], 0, None))
    return out


def _fallback_threshold(level, feature):
    feature_thresholds = RULE_THRESHOLDS["aggregation_levels"][level]["features"].get(feature, {})
    values = [v for v in feature_thresholds.values() if v.get("lower") is not None and v.get("upper") is not None]
    if not values:
        return {"lower": 0.0, "upper": 0.0, "iqr": 1.0, "direction": RULE_DIRECTIONS[feature]}
    return {
        "lower": float(np.median([v["lower"] for v in values])),
        "upper": float(np.median([v["upper"] for v in values])),
        "iqr": float(np.median([v.get("iqr") or 1.0 for v in values])),
        "direction": RULE_DIRECTIONS[feature],
    }


def _get_threshold(level, equipment_id, feature):
    feature_thresholds = RULE_THRESHOLDS["aggregation_levels"][level]["features"].get(feature, {})
    threshold = feature_thresholds.get(equipment_id)
    if threshold is None:
        threshold = _fallback_threshold(level, feature)
    return threshold


def _score_iqr(row):
    level = row["aggregation_level"]
    equipment_id = row["equipment_id"]
    triggered = []
    values = {}
    thresholds = {}
    directions = {}
    scores = []

    for feature, direction in RULE_DIRECTIONS.items():
        threshold = _get_threshold(level, equipment_id, feature)
        lower = threshold.get("lower")
        upper = threshold.get("upper")
        iqr = threshold.get("iqr") or 0
        value = _to_float(row.get(feature))
        if lower is None or upper is None:
            continue
        denom = iqr if iqr not in [None, 0] and np.isfinite(iqr) else max(abs(upper - lower), 1e-9)
        if direction == "high":
            is_triggered = value > upper
            score = max(0.0, (value - upper) / denom * 100)
            reason = f"{feature}_high"
        else:
            is_triggered = value < lower
            score = max(0.0, (lower - value) / denom * 100)
            reason = f"{feature}_low"
        score = float(np.clip(score, 0, 100))
        scores.append(score)
        if is_triggered:
            triggered.append(feature)
            values[feature] = float(value)
            thresholds[feature] = {"lower": float(lower), "upper": float(upper)}
            directions[feature] = direction

    rule_score = float(np.clip(max(scores) if scores else 0.0, 0, 100))
    rule_reason = "|".join([f"{feature}_{RULE_DIRECTIONS[feature]}" for feature in triggered]) if triggered else "normal"
    return {
        "rule_anomaly": 1 if triggered else 0,
        "rule_score": rule_score,
        "rule_reason": rule_reason,
        "triggered_features": triggered,
        "triggered_feature_values": values,
        "threshold_values": thresholds,
        "threshold_direction": directions,
    }


def _build_feature_matrix(rows, level):
    feature_columns = FEATURE_CONFIG["model_features_by_aggregation"][level]
    matrix_rows = []
    for row in rows:
        feature_values = {col: 0.0 for col in feature_columns}
        for col in FEATURE_CONFIG["base_anomaly_features"]:
            if col in feature_values:
                feature_values[col] = _to_float(row.get(col))
        one_hot_col = f"equipment_id_{row['equipment_id']}"
        if one_hot_col in feature_values:
            feature_values[one_hot_col] = 1.0
        matrix_rows.append([feature_values[col] for col in feature_columns])
    return pd.DataFrame(matrix_rows, columns=feature_columns, dtype=np.float32)


def _scale_iforest_scores(level, raw_scores):
    abnormal = -np.asarray(raw_scores, dtype=float)
    metadata = FINAL_SCORE_LOGIC.get("model_metadata", {}).get(level, {})
    scale = metadata.get("score_scale", {})
    lower = scale.get("lower_percentile_1")
    upper = scale.get("upper_percentile_99")
    if lower is not None and upper is not None and np.isfinite(lower) and np.isfinite(upper) and upper > lower:
        return np.clip((abnormal - lower) / (upper - lower) * 100, 0, 100)
    lo = np.nanmin(abnormal)
    hi = np.nanmax(abnormal)
    if not np.isfinite(lo) or not np.isfinite(hi) or hi <= lo:
        # Single-row safe fallback: map negative decision values upward but keep bounded.
        return np.clip(50 + abnormal * 250, 0, 100)
    return np.clip((abnormal - lo) / (hi - lo) * 100, 0, 100)


def _score_iforest(rows_by_level):
    scored = {}
    for level, indexed_rows in rows_by_level.items():
        rows = [row for _, row in indexed_rows]
        x = _build_feature_matrix(rows, level)
        x_scaled = SCALERS[level].transform(x)
        pred = MODELS[level].predict(x_scaled)
        raw = MODELS[level].decision_function(x_scaled)
        score = _scale_iforest_scores(level, raw)
        for (idx, _), pred_value, raw_value, score_value in zip(indexed_rows, pred, raw, score):
            scored[idx] = {
                "iforest_anomaly": 1 if int(pred_value) == -1 else 0,
                "iforest_score_raw": float(raw_value),
                "iforest_score": float(np.clip(score_value, 0, 100)),
            }
    return scored


def _final_level(score):
    if score < 30:
        return "normal"
    if score < 50:
        return "watch"
    if score < 75:
        return "warning"
    return "critical"


def _recommended_action(rule_reason, iforest_anomaly):
    if rule_reason and rule_reason != "normal":
        actions = []
        for reason in rule_reason.split("|"):
            action = ACTION_MAP.get(reason)
            if action and action not in actions:
                actions.append(action)
        return "; ".join(actions) if actions else "이상 원인 세부 확인"
    if iforest_anomaly:
        return "다변량 패턴 이상 여부 점검"
    return "정기 모니터링 유지"


def _final_reason(row, rule_result, iforest_result, final_level):
    if rule_result["triggered_features"]:
        features = ", ".join(rule_result["triggered_features"])
        return (
            f"{row['equipment_id']} 설비가 {row['window_end_time']} 기준 {features} 항목에서 기준을 벗어났고, "
            f"IsolationForest 점수 {iforest_result['iforest_score']:.1f}로 {final_level} 이상 후보로 분류되었습니다."
        )
    if iforest_result["iforest_anomaly"]:
        return (
            f"{row['equipment_id']} 설비가 {row['window_end_time']} 기준 단일 Rule 기준 초과는 없으나, "
            f"IsolationForest 기준 다변량 패턴이 정상 구간과 달라 {final_level} 이상 후보로 분류되었습니다."
        )
    return (
        f"{row['equipment_id']} 설비는 {row['window_end_time']} 기준 최종 이상 점수가 "
        f"{final_level} 범위로 분류되었습니다."
    )


def _data_quality(row):
    reasons = []
    event_count = _to_float(row.get("event_count"))
    expected = EXPECTED_EVENT_COUNTS.get(row["aggregation_level"], 0)
    if event_count <= 0 or (expected and event_count < expected * 0.2):
        reasons.append("event_count_missing_or_low")
    if "completeness_ratio" in row and _to_float(row.get("completeness_ratio"), 1.0) < 0.8:
        reasons.append("completeness_ratio_below_0.8")
    return {
        "data_quality_issue_flag": 1 if reasons else 0,
        "data_quality_reason": "|".join(reasons) if reasons else "normal",
    }


def _make_output(row, rule_result, iforest_result):
    level = row["aggregation_level"]
    weights = FINAL_SCORE_LOGIC.get("score_weights", {}).get(level, {})
    rule_weight = float(weights.get("rule", 0.55 if level != "1d" else 0.60))
    iforest_weight = float(weights.get("iforest", 0.45 if level != "1d" else 0.40))
    reference_only = bool(weights.get("reference_only", level == "1d"))

    rule_contribution = float(rule_result["rule_score"] * rule_weight)
    iforest_contribution = float(iforest_result["iforest_score"] * iforest_weight)
    final_score = float(np.clip(rule_contribution + iforest_contribution, 0, 100))
    final_level = _final_level(final_score)
    model_vote_count = int(rule_result["rule_anomaly"] + iforest_result["iforest_anomaly"])
    if rule_result["rule_anomaly"] and iforest_result["iforest_anomaly"]:
        primary = "rule_based+isolation_forest"
    elif rule_result["rule_anomaly"]:
        primary = "rule_based"
    elif iforest_result["iforest_anomaly"]:
        primary = "isolation_forest"
    else:
        primary = "none"
    quality = _data_quality(row)

    return {
        "equipment_id": row["equipment_id"],
        "window_end_time": row["window_end_time"],
        "aggregation_level": level,
        "rule_anomaly": int(rule_result["rule_anomaly"]),
        "rule_score": float(rule_result["rule_score"]),
        "rule_reason": rule_result["rule_reason"],
        "triggered_features": rule_result["triggered_features"],
        "triggered_feature_values": rule_result["triggered_feature_values"],
        "threshold_values": rule_result["threshold_values"],
        "threshold_direction": rule_result["threshold_direction"],
        "iforest_anomaly": int(iforest_result["iforest_anomaly"]),
        "iforest_score": float(iforest_result["iforest_score"]),
        "iforest_score_raw": float(iforest_result["iforest_score_raw"]),
        "final_anomaly_score": final_score,
        "final_anomaly_level": final_level,
        "primary_anomaly_model": primary,
        "model_vote_count": model_vote_count,
        "strong_anomaly_candidate": int(model_vote_count >= 2),
        "critical_candidate": int(final_level == "critical" or final_score >= 75),
        "rule_contribution": rule_contribution,
        "iforest_contribution": iforest_contribution,
        "final_reason": _final_reason(row, rule_result, iforest_result, final_level),
        "recommended_action": _recommended_action(rule_result["rule_reason"], iforest_result["iforest_anomaly"]),
        "data_quality_issue_flag": int(quality["data_quality_issue_flag"]),
        "data_quality_reason": quality["data_quality_reason"],
        "created_at": datetime.now(timezone.utc).isoformat(),
        "reference_only": reference_only,
    }


def _json_safe(value):
    if isinstance(value, dict):
        return {str(k): _json_safe(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_json_safe(v) for v in value]
    if isinstance(value, (np.integer,)):
        return int(value)
    if isinstance(value, (np.floating,)):
        return float(value)
    if isinstance(value, (pd.Timestamp, datetime)):
        return value.isoformat()
    return value


def run(raw_data):
    try:
        if not MODELS:
            init()
        rows = [_prepare_row(row) for row in _parse_raw_data(raw_data)]
        rows_by_level = {level: [] for level in SUPPORTED_LEVELS}
        for idx, row in enumerate(rows):
            rows_by_level[row["aggregation_level"]].append((idx, row))
        rows_by_level = {level: items for level, items in rows_by_level.items() if items}
        iforest_results = _score_iforest(rows_by_level)

        outputs = []
        for idx, row in enumerate(rows):
            rule_result = _score_iqr(row)
            outputs.append(_make_output(row, rule_result, iforest_results[idx]))
        return {"predictions": _json_safe(outputs)}
    except Exception as exc:
        return {"error": str(exc)}
