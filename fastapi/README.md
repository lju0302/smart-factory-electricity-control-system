# 🏭 Smart Factory Power Stream Producer

![FastAPI](https://img.shields.io/badge/FastAPI-005571?style=for-the-badge&logo=fastapi)
![DuckDB](https://img.shields.io/badge/DuckDB-FFF000?style=for-the-badge&logo=duckdb&logoColor=black)
![Azure Event Hub](https://img.shields.io/badge/Azure_Event_Hub-0078D4?style=for-the-badge&logo=microsoft-azure&logoColor=white)
![Python](https://img.shields.io/badge/Python-3776AB?style=for-the-badge&logo=python&logoColor=white)

## 📌 개요 (Overview)

**Smart Factory Power Stream Producer**는 스마트 팩토리 설비의 5초 단위 전력 데이터를 읽어와 **Azure Event Hub**로 실시간 재생(스트리밍)하는 **FastAPI** 기반의 애플리케이션입니다. 

과거의 정적 데이터(DuckDB)를 마치 현재 실시간으로 발생하는 설비 센서 이벤트처럼 시뮬레이션하여 전송함으로써, 스트리밍 파이프라인(예: 실시간 이상 탐지 시스템, 대시보드) 구축 및 테스트를 완벽하게 지원합니다.

---

## ✨ 주요 기능 (Key Features)

- ⚡ **실시간 데이터 스트리밍 시뮬레이션**: DuckDB에 저장된 대용량 전력 데이터를 청크 단위로 읽어와 설정된 주기(`interval_seconds`)에 맞춰 비동기적으로 전송합니다.
- ☁️ **Azure Event Hub 완벽 연동**: `azure-eventhub` 라이브러리를 활용하여 클라우드로 안전하고 빠르게 이벤트를 전송합니다.
- 🧪 **이상치 주입 (Anomaly Injection)**: 데모 및 테스트를 위해 정상 전력 데이터에 합성 이상치(Synthetic Anomaly)를 실시간으로 주입하는 기능을 지원합니다. (`/stream/start` 호출 시 옵션 제공)
- ⏱️ **이벤트 타임스탬프 동기화**: 원본 과거 데이터의 시간(`source_timestamp`)을 보존하면서도, Event Hub 전송 시점의 현재 UTC 시간(`event_time`)으로 자동 변환하여 스트리밍 시스템에 적합한 형태를 제공합니다.
- 🛠️ **안전한 Dry Run 모드**: 클라우드 리소스를 낭비하지 않고도 로컬에서 데이터 송신 형태와 양을 테스트할 수 있는 `dry_run` 모드를 기본 지원합니다.

---

## 🏗️ 프로젝트 구조 (Project Structure)

```text
fastapi/
├── app/
│   ├── main.py               # FastAPI 애플리케이션 엔트리포인트 및 API 라우터
│   ├── config.py             # 환경 변수 및 설정 관리 (pydantic/dotenv)
│   ├── schemas.py            # API 요청/응답 Pydantic 모델
│   ├── stream_manager.py     # 스트리밍 백그라운드 태스크 관리 및 제어
│   ├── eventhub_sender.py    # Azure Event Hub 메시지 전송 로직
│   ├── data_loader.py        # DuckDB 데이터 조회 및 청크 분할
│   └── anomaly_injector.py   # 합성 이상치(Anomaly) 주입 로직
├── data/                     # 원본 Parquet 데이터 폴더
├── db/
│   └── smart_factory.duckdb  # 정제된 전력 데이터가 저장된 DuckDB 파일
├── requirements.txt          # 파이썬 의존성 패키지 목록
└── .env                      # 환경 변수 파일 (Git에서 제외됨)
```

---

## ⚙️ 환경 변수 (Environment Variables)

프로젝트 루트에 `.env` 파일을 생성하고 다음 변수들을 설정합니다.

```env
# DuckDB 설정
DUCKDB_PATH="./db/smart_factory.duckdb"
DUCKDB_TABLE="power_clean"

# Azure Event Hub 설정
EVENTHUB_CONNECTION_STR="Endpoint=sb://<REDACTED><your-namespace>.servicebus.windows.net/;SharedAccessKeyName=...;SharedAccessKey=..."
EVENTHUB_NAME="<your-eventhub-name>"

# 스트리밍 기본 설정
DEFAULT_INTERVAL_SECONDS="0.5"
DEFAULT_CHUNK_TIMESTAMPS="20"

# 테스트 모드 (실제 Event Hub 전송 여부)
DRY_RUN="true" # true로 설정 시 콘솔에만 출력됨
```

---

## 🚀 API 엔드포인트 (API Endpoints)

FastAPI에서 제공하는 Swagger UI (`/docs`)를 통해 브라우저에서 직접 테스트할 수 있습니다.

### 시스템 상태 및 데이터 조회
- `GET /health`: 서버 및 DB 연결 상태, Dry Run 여부를 확인합니다.
- `GET /sample?limit={limit}`: DuckDB에서 샘플 전력 데이터를 조회하여 반환합니다.

### 스트리밍 제어
- `POST /stream/start`: 전력 데이터 스트리밍을 시작합니다. (비동기 백그라운드 태스크 실행)
  - **Body (JSON)**: `start_timestamp`, `interval_seconds`, `inject_demo_anomaly` 등 세부 제어 옵션 전달 가능.
- `POST /stream/stop`: 현재 실행 중인 스트리밍을 강제로 중지합니다.
- `GET /stream/status`: 현재 스트리밍의 실행 여부(`is_running`), 전송된 이벤트 수(`sent_events`), 마지막 전송 타임스탬프 등을 실시간으로 확인합니다.

---

## 💻 시작하기 (Getting Started)

### 1. 가상 환경 설정 및 패키지 설치
```bash
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

### 2. 애플리케이션 실행
```bash
# uvicorn을 사용하여 FastAPI 서버를 실행합니다.
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

### 3. API 문서 확인
웹 브라우저에서 `http://localhost:8000/docs` 에 접속하여 Swagger UI를 통해 제공되는 API를 확인하고 직접 스트리밍을 시작해보세요!

### 4. 사용 예시
```bash
# 별도의 터미널에서 실행
# 1. 서버 상태 확인
curl -X POST "http://localhost:8000/health"       

# 2. 스트림 현황 확인, sent_timestamp_groups 1 증가할 때마다 sent_events는 13씩 증가
curl "http://localhost:8000/stream/status"        

# 3. 스트림 시작  
curl -X POST "http://localhost:8000/stream/start" \
  -H "Content-Type: application/json" \
  -d '{
    "interval_seconds": 0.5,
    "chunk_timestamps": 5,
    "inject_demo_anomaly": false
  }'

# 4. 스트림 정지
curl -X POST "http://localhost:8000/stream/stop"  

```