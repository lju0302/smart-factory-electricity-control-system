# Azure ML Anomaly Detection Package

이 패키지는 2025년 3월까지의 데이터를 기준으로 학습/계산한 이상탐지 아티팩트를 Azure Machine Learning custom model endpoint에서 테스트하기 위한 패키지다.

## 목적

입력 feature row를 받아 IQR Rule-Based와 IsolationForest를 적용하고, Azure/Power BI 모니터링용 output schema에 맞춘 이상 후보 결과를 반환한다.

## 모델 구조

- IQR Rule-Based: `rule_thresholds_train_through_march.json`의 설비별 threshold를 사용한다.
- IsolationForest: aggregation level별 `isolation_forest_<level>.joblib` 모델과 `standard_scaler_<level>.joblib` scaler를 사용한다.
- 최종 점수: IQR 점수와 IsolationForest 점수를 가중합한다.

## 지원 aggregation_level

- `1m`: 운영 모니터링 대상
- `15m`: 운영 모니터링 대상
- `1h`: 운영 모니터링 대상
- `1d`: reference-only. 운영 알람 대상에서 분리하는 것을 권장한다.

## 입력 JSON 예시

`sample_request.json` 참고.

```json
{
  "data": [
    {
      "equipment_id": "13(3호기)",
      "window_end_time": "2025-04-15T23:45:00",
      "aggregation_level": "15m",
      "avg_voltage_r": 221.0,
      "avg_voltage_s": 218.5,
      "avg_voltage_t": 220.2,
      "avg_current_r": 31.0,
      "avg_current_s": 44.0,
      "avg_current_t": 20.0,
      "avg_power_factor": 72.0,
      "avg_voltage_imbalance_rate": 4.5,
      "avg_current_imbalance_rate": 46.0,
      "event_count": 180,
      "rolling_15m_peak_kW": 28.0,
      "carbon_emission_kg": 2.8,
      "kepco_10m_v_imb": 3.8,
      "kepco_10m_c_imb": 38.0,
      "kepco_30m_pf": 76.0,
      "hour": 23,
      "dayofweek": 1,
      "is_weekend": 0,
      "completeness_ratio": 1.0
    }
  ]
}
```

## 출력 JSON 예시

`sample_response.json` 참고. 주요 출력은 다음을 포함한다.

- `rule_anomaly`, `rule_score`, `rule_reason`
- `triggered_features`, `triggered_feature_values`, `threshold_values`, `threshold_direction`
- `iforest_anomaly`, `iforest_score`, `iforest_score_raw`
- `final_anomaly_score`, `final_anomaly_level`
- `final_reason`, `recommended_action`
- `data_quality_issue_flag`, `data_quality_reason`
- `reference_only`

## Azure ML 배포 시 필요한 파일

```text
ml_package/
  score.py
  requirements.txt
  models/
  config/
```

Azure ML custom scoring script는 `score.py`를 entry script로 사용한다.

## score.py 구조

- `init()`: 모델, scaler, threshold, feature column, score logic, output schema를 로드한다. Azure에서는 `AZUREML_MODEL_DIR`을 우선 사용하고, 로컬에서는 현재 파일 기준 상대 경로를 fallback으로 사용한다.
- `run(raw_data)`: JSON string/dict/list 입력을 받아 단일 row 또는 batch scoring을 수행한다.

## 주의 사항

- `critical`은 확정 고장이 아니라 우선 점검 후보이다.
- `warning`은 주의/점검 후보, `watch`는 관찰 필요, `normal`은 정상 범위이다.
- `1d`는 reference-only이며 운영 알람 대상에서 제외할 수 있도록 `reference_only=true`로 반환한다.
- LOF는 streaming inference와 Azure 패키징 관점에서 운영 primary 모델에서 제외했다.
- Forecast Error는 수치예측 모델의 R2가 낮아 운영 primary score에는 포함하지 않았다.

## 로컬 테스트

```bash
cd ml_package
python test_score_local.py
```

실행 후 `sample_response.json`과 `package_validation_report.md`가 생성된다.
