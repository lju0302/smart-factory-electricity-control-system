# 운영·배포 가이드

## 로컬 FastAPI 실행

```bash
cd fastapi
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.template .env
uvicorn app.main:app --reload
```

기본 확인 순서:

```bash
curl http://127.0.0.1:8000/health
curl http://127.0.0.1:8000/sample
curl http://127.0.0.1:8000/stream/status
```

실제 Event Hubs와 SQL을 연결할 때는 `.env`와 `local.settings.json`을 저장소에 커밋하지 않습니다.

## 환경 설정

| 설정 | 주입 위치 | 용도 |
| --- | --- | --- |
| Event Hubs 연결 정보 | Function App 설정 또는 Key Vault | 이벤트 입력·출력 |
| SQL 연결 정보 | Function App 설정 또는 Key Vault | 집계·분석 결과 저장 |
| Teams/Power Automate webhook | Alert Function 설정 | 운영 알림 |
| 모델·임계값 artifact | 비공개 Blob/배포 artifact | 추론 기준 |

운영 값은 템플릿 파일의 빈 값에 직접 커밋하지 말고 배포 단계에서 주입합니다.

## IaC 배포 순서

1. `infra/` 변경을 로컬에서 Bicep build로 확인합니다.
2. GitHub Actions의 `Infra What-If`를 대상 환경에 실행합니다.
3. 리소스 변경·삭제·권한 변경을 검토합니다.
4. 승인 후 `Deploy Infra (dev)`를 실행합니다.
5. Azure Portal 또는 CLI에서 Event Hubs, Stream Analytics, Function App 상태를 확인합니다.
6. 애플리케이션 artifact와 비밀 설정을 별도 배포합니다.
7. 샘플 이벤트 1건, 1분 집계, 이상 결과, 알림까지 순서대로 검증합니다.

현재 workflow에는 IaC 검증, 수동 what-if, dev 인프라 배포가 포함되어 있습니다. 운영 환경 배포는 승인 정책과 별도 workflow를 확정한 뒤 추가합니다.

## 검증 명령

로컬에 Azure CLI와 Bicep이 설치되어 있다면 다음을 실행합니다.

```bash
az bicep build --file infra/main.bicep
```

배포 전에는 what-if 결과에서 다음 항목을 확인합니다.

- Event Hubs 이름과 consumer group
- Stream Analytics 입력·출력 연결
- SQL 연결 설정의 secret reference
- Function App의 런타임과 application settings
- Key Vault 접근 권한

## 장애 대응

### 이벤트가 들어오지 않는 경우

1. FastAPI `/api/stream/status`를 확인합니다.
2. `power-events`의 incoming messages와 consumer group을 확인합니다.
3. Stream Analytics job 상태와 입력 미리보기를 확인합니다.
4. 연결 문자열을 코드나 로그에 출력하지 않고 secret reference를 재검증합니다.

### 집계가 생성되지 않는 경우

1. `poweroutput`과 `poweroutput_15m` 출력 오류를 확인합니다.
2. `localtime_datetime` 형식과 타임존을 확인합니다.
3. SQL 대상 테이블의 최근 수신 시각을 확인합니다.
4. 1시간·1일 프로시저의 처리 구간과 마지막 성공 실행을 확인합니다.

### 알림이 중복되거나 누락되는 경우

1. `anomaly_event`의 상태와 이벤트 식별자를 확인합니다.
2. Alert Function 재시도 로그를 확인합니다.
3. Power Automate/Teams webhook 응답과 rate limit을 확인합니다.
4. 수동 재전송 전 중복 방지 키를 확인합니다.

## 롤백 기준

- IaC 변경은 what-if에서 확인된 리소스 범위만 되돌립니다.
- 쿼리·프로시저 변경은 이전 커밋의 artifact로 복원한 뒤 재처리 범위를 기록합니다.
- 비밀값 노출이 의심되면 해당 키·비밀번호·webhook을 즉시 폐기하고 재발급합니다.
- 이미 생성된 집계·알림 이벤트는 삭제하지 말고 영향을 받은 시간 구간과 상태를 기록합니다.
