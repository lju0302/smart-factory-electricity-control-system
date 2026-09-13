# Phase 1 보안 검사 기록

## 기준

- 검사 원본: 사용자가 제공한 Google Drive 폴더
- 검사 시점: 2026-09-13
- 대상: Azure Functions 설정, FastAPI 환경 파일, forecast DB 설정, ML 모델 보관 경로

## 조치 결과

- 원본 자격 증명 파일은 안전 기준 트리에 포함하지 않았습니다.
- 공개 저장소에 필요한 템플릿만 생성했고, 비밀 값은 모두 빈 문자열로 바꿨습니다.
- `*.joblib`, DuckDB, CSV/Parquet, Azurite 상태 파일을 추적 제외했습니다.
- 원본 Drive 파일은 읽기만 수행했습니다.

## 보호 대상 목록

| 유형 | 확인된 키/파일 | 처리 |
|---|---|---|
| SQL | `SqlTriggerConnectionString`, `SqlOdbcConnectionString`, `SQL_CONNECTION_STRING` | 템플릿 빈 값 |
| SQL 계정 | `SQL_PASSWORD`, `DB_PASSWORD` | 템플릿 빈 값 |
| Event Hub | `EVENTHUB_CONNECTION_STR`, `EventHubConnectionString` | 템플릿 빈 값 |
| Teams | `TEAMS_WEBHOOK_URL`, `TEAMS_ALERT_WEBHOOK_URL` | 템플릿 빈 값 |
| 모델 | `models/**/*.joblib` | Git 제외, `.gitkeep`만 유지 |

## 남은 위험

Drive 원본에는 이미 자격 증명이 들어간 파일이 존재합니다. Phase 3에서 공개 원격 저장소로 전환하기 전에 해당 자격 증명을 회전하고, 공개 저장소 이력에 원본이 들어가지 않았는지 별도로 확인해야 합니다. 이미 노출된 비밀번호·연결 문자열·webhook은 폐기 및 재발급을 권장합니다.

