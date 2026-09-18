# 공개 저장소 보안 검사 기록

## 기준

- 검사 원본: 사용자가 제공한 Google Drive 폴더와 GitHub `main`
- 검사 시점: 2026-09-18
- 대상: Azure Functions 설정, FastAPI 환경 파일, SQL 연결 설정, ML 모델·임계값 경로, GitHub 공개 이력

## 조치 결과

- 원본 자격 증명 파일은 공개 저장소에 포함하지 않았습니다.
- `local.settings.json`, `.env`는 템플릿만 유지하고 실제 값은 제외했습니다.
- `*.joblib`, DuckDB, CSV/Parquet, Azurite 상태 파일은 추적 대상에서 제외했습니다.
- 소스코드는 복원했지만 비밀값과 운영 데이터는 복원 범위에서 제외했습니다.
- 설비별 학습 통계와 운영 임계값이 담긴 `rule_thresholds_train_through_march.json`은 공개 Git에 넣지 않았습니다. 추론 배포 시 비공개 artifact 또는 Blob에서 주입해야 합니다.

## 보호 대상

| 유형 | 키·파일 예시 | 처리 |
| --- | --- | --- |
| SQL | `SqlTriggerConnectionString`, `SqlOdbcConnectionString`, `SQL_CONNECTION_STRING` | 템플릿 빈 값 또는 secret reference |
| SQL 계정 | `SQL_PASSWORD`, `DB_PASSWORD` | 공개 저장소 제외 |
| Event Hubs | `EVENTHUB_CONNECTION_STR`, `EventHubConnectionString` | 공개 저장소 제외 |
| 알림 | `TEAMS_WEBHOOK_URL`, `TEAMS_ALERT_WEBHOOK_URL` | 공개 저장소 제외 |
| 모델 | `models/**/*.joblib` | Git 제외, 배포 artifact로 주입 |
| 학습 임계값 | `rule_thresholds_train_through_march.json` | 비공개 artifact로 주입 |

## 공개 이력 확인

현재 `main` 트리와 복원된 소스에서 다음 유형의 실제 값이 포함되지 않았는지 확인했습니다.

- Drive 원본에 포함된 것으로 확인된 기존 SQL 비밀번호 값
- `SharedAccessKey`
- 실제 Azure SQL 호스트 연결 문자열

환경 변수 이름과 템플릿의 빈 키는 문서·설정 예시에 남을 수 있습니다. 키 이름의 존재와 실제 비밀값의 존재를 구분해 검토합니다.

## 남은 위험과 후속 조치

Drive 원본에는 이미 자격 증명이 들어간 파일이 있을 수 있습니다. 공개 저장소 반영과 별개로 해당 비밀번호·연결 문자열·webhook은 폐기 및 재발급해야 합니다. 공개 Git 이력에서 노출이 확인되면 현재 파일만 수정하지 말고 관련 키를 즉시 회전하고, 필요하면 이력 정리 절차를 별도로 승인받습니다.

모델과 학습 임계값 artifact는 CI 로그·PR 첨부·공개 Blob에 노출하지 않습니다. 배포 전 private storage 접근 권한과 Function App 설정 주입 여부를 확인합니다.
