# Smart Factory Electricity Control System

스마트 팩토리 설비의 전력 데이터를 실시간으로 수집·집계하고, 이상 징후와 수요를 분석해 운영자에게 전달하는 데이터·ML 기반 전력 관제 시스템입니다.

## 프로젝트 개요

설비 전력 데이터는 5초 단위로 수집되지만 운영자가 모든 원천 이벤트를 직접 확인하기는 어렵습니다. 이 프로젝트는 원천 데이터를 운영 가능한 시간 단위로 집계하고, 전력 품질 이상·설비 이상·수요 예측·알림을 하나의 파이프라인으로 연결합니다.

스트리밍된 전력 데이터는 Azure Event Hubs와 Stream Analytics를 거쳐 시간 단위 마트로 정제되며, ML 모델이 설비별 이상 징후와 미래 전력 수요를 분석합니다. 분석 결과는 Power BI 대시보드, Teams 알림, 일일 리포트로 제공되어 현장 운영자가 설비 상태를 빠르게 파악하고 점검 우선순위를 결정할 수 있도록 합니다.

## 주요 처리 흐름

1. DuckDB의 과거 전력 데이터를 FastAPI가 실시간 센서 이벤트처럼 재생합니다.
2. Azure Event Hubs가 이벤트 스트림을 수신합니다.
3. Azure Stream Analytics와 SQL 처리 계층이 1분·15분·1시간·1일 마트를 생성합니다.
4. 이상탐지 계층이 Rule/IQR와 Isolation Forest를 이용해 이상 후보를 계산합니다.
5. 예측 계층이 NHITS와 TFT 모델로 설비별 전력 수요를 예측합니다.
6. 리포트·알림 계층이 결과를 Microsoft Teams, 이메일, Power BI로 제공합니다.

## 전체 아키텍처

    과거 전력 데이터
            |
            v
    FastAPI Stream Producer
            |
            v
    Azure Event Hubs
            |
            v
    Azure Stream Analytics
       /              \
      v                v
    SQL 1분/15분 마트   Anomaly Event Hub
      |                |
      v                v
    SQL 집계 Timer      Anomaly Detection Function
      |                |
      v                +--> anomaly_predictions
    SQL 1시간/1일 마트  +--> anomaly_event
      |                         |
      +--> Forecast Function    v
      |    NHITS / TFT       Alert Dispatcher
      |                         |
      +--> Daily Report         v
             |             Power Automate
             |                  |
             +---------> Teams / Email

    SQL 마트 + Forecast Result
                |
                v
           Power BI Dashboard

## 레이어별 역할

### 1. Streaming Layer

fastapi/는 DuckDB에 저장된 전력 데이터를 읽어 실시간 이벤트처럼 재생하는 FastAPI 애플리케이션입니다.

- /health: API와 DB 상태 확인
- /sample: 샘플 데이터 조회
- /stream/start: 스트리밍 시작
- /stream/stop: 스트리밍 중지
- /stream/status: 전송 상태 조회
- 합성 이상치 주입을 통한 데모와 통합 테스트
- DRY_RUN 모드를 이용한 로컬 테스트

주요 모듈은 app/main.py, stream_manager.py, data_loader.py, eventhub_sender.py, anomaly_injector.py입니다.

### 2. Storage & SQL Processing Layer

원천 이벤트는 Stream Analytics와 SQL 처리 계층을 거쳐 운영 조회용 마트로 변환됩니다.

- 1분·15분 단위 전력 집계
- Stored Procedure를 이용한 1시간·1일 집계
- 데이터 수집 완료 상태와 리포트 처리 상태 기록
- 이상 예측 결과와 알림 이벤트 상태 관리
- 로컬 개발용 DuckDB와 Azure SQL 운영 환경 분리

fastapi/sql-timer-trigger/는 주기적으로 SQL 집계 프로시저를 실행하는 Azure Function 영역입니다.

### 3. ML & Automation Layer

#### Anomaly Detection

ml_package/는 입력 feature row 또는 batch를 받아 이상 후보를 계산하는 scoring 패키지입니다.

- 설비별 IQR/Rule threshold
- aggregation level별 Isolation Forest와 scaler
- Rule score와 모델 score를 결합한 최종 점수
- normal, watch, warning, critical 등급
- reference_only를 통한 1일 단위 reference 결과 분리
- 데이터 품질 문제와 추천 조치 반환

모델 파일은 저장소에 커밋하지 않고 별도 모델 저장소나 배포 아티팩트로 관리합니다.

#### Demand Forecast

mlforecast/는 15분 집계 데이터를 기반으로 설비별 전력 수요를 예측하는 영역입니다.

- NHITS 모델
- TFT 모델
- src/inference.py 기반 추론
- src/db.py 기반 입력 조회 및 예측 결과 저장
- models/NHITS와 models/TFT 경로 기반 모델 관리

#### Daily Report

functions/는 1일 집계 결과를 읽어 전체 설비 상태, 이상 후보, 데이터 완전성, 주요 인사이트를 계산하고 HTML/Markdown 일일 리포트를 생성하는 Azure Function 영역입니다.

#### Alert Dispatcher

power-anomaly-alert-function/은 이상탐지 모델을 직접 실행하지 않습니다.

    Detection Logic
    -> dbo.anomaly_event (PENDING)
    -> Alert Dispatcher
    -> Power Automate HTTP Workflow
    -> Microsoft Teams

발송 성공 시 SENT, 실패 시 FAILED로 상태를 갱신하고 재시도 횟수를 관리합니다.

## 저장 데이터와 주요 상태

| 데이터 | 역할 |
|---|---|
| 원천 전력 이벤트 | 설비별 전압·전류·전력 품질 지표 |
| 1분·15분 마트 | 실시간 모니터링과 ML 입력 |
| 1시간·1일 마트 | 리포트·장기 분석·Power BI |
| anomaly_predictions | 이상 계산 결과와 근거 |
| anomaly_event | 알림 발송 대기·성공·실패 상태 |
| Forecast Result | 설비별 미래 전력 수요 예측 |
| Report/Status Log | 집계·예측·리포트 처리 상태와 중복 방지 |

## 저장소 구조

    .
    ├── fastapi/
    │   ├── app/
    │   │   ├── main.py
    │   │   ├── config.py
    │   │   ├── schemas.py
    │   │   ├── stream_manager.py
    │   │   ├── eventhub_sender.py
    │   │   ├── data_loader.py
    │   │   └── anomaly_injector.py
    │   ├── db/
    │   └── sql-timer-trigger/
    ├── functions/
    │   └── function_app.py
    ├── mlforecast/
    │   ├── src/
    │   │   ├── config.py
    │   │   ├── db.py
    │   │   ├── inference.py
    │   │   ├── model_loader.py
    │   │   └── utils.py
    │   └── models/
    ├── ml_package/
    │   ├── score.py
    │   ├── config/
    │   └── models/
    ├── power-anomaly-alert-function/
    │   ├── function_app.py
    │   └── sql/
    ├── infra/                         # Azure IaC 예정
    ├── .github/workflows/             # CI/CD 예정
    └── security-audit.md

## 로컬 실행

### FastAPI 스트리밍

    cd fastapi
    python -m venv .venv
    source .venv/bin/activate
    pip install -r requirements.txt
    uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

Swagger UI는 http://localhost:8000/docs에서 확인할 수 있습니다.

### Anomaly scoring

    cd ml_package
    python test_score_local.py

## Azure 실행 흐름

    FastAPI Producer
    -> Event Hubs
    -> Stream Analytics / SQL
    -> Forecast & Anomaly Functions
    -> Daily Report & Alert Dispatcher
    -> Teams / Email / Power BI

## 환경 변수와 보안

실제 환경 변수와 연결 정보는 Git에 커밋하지 않습니다.

- local.settings.json
- .env와 .env.local
- SQL password와 connection string
- Event Hub connection string
- Teams webhook
- DuckDB와 원천 데이터
- joblib 모델 파일

템플릿과 제외 규칙은 각 프로젝트 디렉터리에 있습니다. 보안 점검 결과는 security-audit.md에서 확인할 수 있습니다.

## IaC 방향

Azure 리소스는 infra/ 아래 Bicep 모듈로 관리할 예정입니다.

- 환경별 Resource Group
- Storage, Event Hubs, Azure SQL
- Key Vault와 Managed Identity
- Function App과 Application Insights
- GitHub Actions OIDC 기반 배포
- Pull Request의 lint, build, what-if
- production 환경 승인 후 배포

기존 Azure 리소스를 신규 생성할지 참조할지는 IaC 적용 단계에서 확정합니다.

## 현재 GitHub 반영 상태

현재 main에는 Phase 1 보안 기준, 환경 변수 템플릿, 모델 바이너리 제외 규칙이 반영되어 있습니다. 애플리케이션 소스 이관과 infra 구현은 다음 커밋 단위에서 진행합니다.
