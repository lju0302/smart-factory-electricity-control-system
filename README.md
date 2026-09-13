# GitHub Repository Phase 1 — Secure Baseline

Drive 원본을 기준으로 만든 Phase 1 산출물입니다. 이 디렉터리에는 공개 저장소에 포함할 수 있는 설정 템플릿과 Git 제외 규칙만 들어 있습니다.

## 완료 범위

- `local.settings.json`, `.env`, `.env.local` 원본은 산출물에 복사하지 않았습니다.
- SQL 비밀번호, SQL 연결 문자열, Event Hub 연결 문자열, Teams webhook 값은 템플릿에서 비워 두었습니다.
- 프로젝트 루트별 `.gitignore`에 환경 파일, DuckDB, 모델 바이너리, 로컬 실행 산출물을 등록했습니다.
- `*.joblib`는 저장소에 넣지 않도록 전역·프로젝트별 규칙에 포함했습니다.

## 원본에서 확인된 보호 대상

| 원본 경로 | 보호 대상 |
|---|---|
| `functions/local.settings.json` | SQL 연결 문자열, Teams webhook |
| `fastapi/.env` | `EVENTHUB_CONNECTION_STR` |
| `fastapi/sql-timer-trigger/local.settings.json` | SQL 연결 문자열 |
| `mlforecast/local.settings.json` | `SQL_PASSWORD` |
| `mlforecast/.env` | `SQL_PASSWORD` |
| `mlforecast/.env.local` | 로컬 실행 설정 |
| `ml_package/local.settings.json` | Event Hub 연결 문자열, DB 비밀번호, Teams webhook |
| `power-anomaly-alert-function/local.settings.json` | SQL 연결 문자열, Teams webhook |

## 사용 방법

1. 각 프로젝트 디렉터리의 `*.template.*` 파일을 복사해 로컬 설정 파일을 만듭니다.
2. 실제 값은 Azure Functions 설정, Secret Manager 또는 로컬 비추적 파일에만 입력합니다.
3. 커밋 전 아래 검사를 실행합니다.

```bash
git grep -nE 'Endpoint=|SharedAccessKey|TEAMS_.*WEBHOOK' -- ':!*.template.*' ':!README.md' ':!security-audit.md' || true
git status --short --ignored
```

Phase 1에서는 GitHub 원격 저장소 생성·push·Drive 원본 수정은 수행하지 않았습니다. 이는 Phase 3의 전환 작업으로 남겨 둡니다.
