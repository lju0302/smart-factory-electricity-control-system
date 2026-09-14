import json
from pathlib import Path

import score


PACKAGE_DIR = Path(__file__).resolve().parent
REQUEST_PATH = PACKAGE_DIR / "sample_request.json"
RESPONSE_PATH = PACKAGE_DIR / "sample_response.json"
REPORT_PATH = PACKAGE_DIR / "package_validation_report.md"


REQUIRED_OUTPUT_COLUMNS = [
    "equipment_id",
    "window_end_time",
    "aggregation_level",
    "rule_anomaly",
    "rule_score",
    "rule_reason",
    "triggered_features",
    "triggered_feature_values",
    "threshold_values",
    "threshold_direction",
    "iforest_anomaly",
    "iforest_score",
    "iforest_score_raw",
    "final_anomaly_score",
    "final_anomaly_level",
    "primary_anomaly_model",
    "model_vote_count",
    "strong_anomaly_candidate",
    "critical_candidate",
    "rule_contribution",
    "iforest_contribution",
    "final_reason",
    "recommended_action",
    "data_quality_issue_flag",
    "data_quality_reason",
    "created_at",
    "reference_only",
]


def main():
    score.init()
    request = json.loads(REQUEST_PATH.read_text(encoding="utf-8"))
    response = score.run(request)
    RESPONSE_PATH.write_text(json.dumps(response, ensure_ascii=False, indent=2), encoding="utf-8")

    predictions = response.get("predictions", [])
    missing = []
    score_range_ok = True
    level_ok = True
    serialization_ok = True
    try:
        json.dumps(response, ensure_ascii=False)
    except TypeError:
        serialization_ok = False

    for row in predictions:
        row_missing = [col for col in REQUIRED_OUTPUT_COLUMNS if col not in row]
        missing.extend(row_missing)
        value = row.get("final_anomaly_score")
        score_range_ok = score_range_ok and isinstance(value, (int, float)) and 0 <= value <= 100
        level_ok = level_ok and row.get("final_anomaly_level") in {"normal", "watch", "warning", "critical"}

    required_files = [
        "score.py",
        "requirements.txt",
        "README.md",
        "sample_request.json",
        "sample_response.json",
        "test_score_local.py",
        "models/isolation_forest_1m.joblib",
        "models/isolation_forest_15m.joblib",
        "models/isolation_forest_1h.joblib",
        "models/isolation_forest_1d.joblib",
        "models/standard_scaler_1m.joblib",
        "models/standard_scaler_15m.joblib",
        "models/standard_scaler_1h.joblib",
        "models/standard_scaler_1d.joblib",
        "config/rule_thresholds_train_through_march.json",
        "config/anomaly_feature_columns.json",
        "config/final_score_logic.json",
        "config/anomaly_output_schema.json",
    ]
    file_rows = []
    for rel in required_files:
        file_rows.append((rel, (PACKAGE_DIR / rel).exists()))

    lines = [
        "# ML Package Validation Report",
        "",
        "## 1. 필수 파일 존재 여부",
        "",
        "| file | exists |",
        "|---|---|",
    ]
    lines.extend([f"| `{rel}` | {exists} |" for rel, exists in file_rows])
    lines.extend(
        [
            "",
            "## 2. 모델/scaler/config 로드 테스트",
            "",
            f"- loaded aggregation levels: {', '.join(score.SUPPORTED_LEVELS)}",
            f"- model count: {len(score.MODELS)}",
            f"- scaler count: {len(score.SCALERS)}",
            "",
            "## 3. sample_request.json scoring 테스트",
            "",
            f"- request rows: {len(request.get('data', []))}",
            f"- response rows: {len(predictions)}",
            f"- response has error: {'error' in response}",
            "",
            "## 4. output schema 컬럼 누락 여부",
            "",
            f"- missing columns: {sorted(set(missing)) if missing else 'none'}",
            "",
            "## 5. final_anomaly_score 범위 검증",
            "",
            f"- all scores within 0~100: {score_range_ok}",
            "",
            "## 6. final_anomaly_level 매핑 검증",
            "",
            f"- all levels valid: {level_ok}",
            "",
            "## 7. JSON serialization 가능 여부",
            "",
            f"- json serializable: {serialization_ok}",
            "",
            "## 8. Azure ML endpoint 배포 전 남은 작업",
            "",
            "- Azure ML workspace에서 `ml_package` 폴더를 custom model로 등록",
            "- `requirements.txt` 또는 동일 dependency를 포함한 Azure ML environment 생성",
            "- Online Endpoint 또는 Batch Endpoint 생성",
            "- 실제 운영 입력 feature 생성 파이프라인과 endpoint 입력 JSON 연결",
            "- 1d 결과는 reference-only로 dashboard/알람에서 분리",
        ]
    )
    REPORT_PATH.write_text("\n".join(lines), encoding="utf-8")
    print(json.dumps(response, ensure_ascii=False, indent=2))
    print(f"Saved {RESPONSE_PATH}")
    print(f"Saved {REPORT_PATH}")


if __name__ == "__main__":
    main()
