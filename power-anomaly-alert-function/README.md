# power-anomaly-alert-function

실시간/준실시간 설비 이상탐지 알림 발신 전용 Azure Function App.

## 역할

이 앱은 이상탐지 모델을 직접 학습하거나 실행하지 않는다.  
ML Studio / 별도 Detection Function / SQL 작업이 `dbo.anomaly_event` 테이블에 이상 이벤트를 `PENDING` 상태로 적재하면, 이 앱이 해당 이벤트를 Teams Workflow로 발송하고 상태를 `SENT` 또는 `FAILED`로 갱신한다.

```text
ML Studio / Detection Logic
→ dbo.anomaly_event(notification_status='PENDING')
→ power-anomaly-alert-function
→ Power Automate HTTP Trigger
→ Microsoft Teams Channel
```

## 주요 파일

```text
function_app.py
requirements.txt
host.json
local.settings.template.json
sql/001_create_anomaly_event.sql
sql/002_insert_dummy_alert.sql
```

## Power Automate 동적 콘텐츠

Teams 게시 액션에서 아래처럼 선택한다.

```text
Message = html
Title 또는 Subject가 있으면 = title
```

조건 분기가 필요하면 다음 필드를 사용한다.

```text
severity
equipment_id
anomaly_type
final_score
```

## 환경변수

```text
SqlOdbcConnectionString
TEAMS_ALERT_WEBHOOK_URL
ALERT_DISPATCH_CRON
MAX_DISPATCH_COUNT
MAX_RETRY_COUNT
```

예시:

```text
ALERT_DISPATCH_CRON=0 */1 * * * *
MAX_DISPATCH_COUNT=20
MAX_RETRY_COUNT=3
```

`ALERT_DISPATCH_CRON=0 */1 * * * *`는 1분마다 PENDING 알림 발송을 시도한다.  
Detection이 15분마다 돌더라도 Dispatcher는 1~5분 주기가 낫다.

## 로컬 실행

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

cp local.settings.template.json local.settings.json
# local.settings.json에 DB 연결 문자열과 TEAMS_ALERT_WEBHOOK_URL 입력

func start
```

수동 발송 테스트:

```bash
curl -X POST http://localhost:7071/api/DispatchAnomalyAlertsManual
```

## SQL 테스트 순서

1. `sql/001_create_anomaly_event.sql` 실행
2. `sql/002_insert_dummy_alert.sql` 실행
3. Function 실행
4. Teams 채널에 알림이 올라오는지 확인
5. `dbo.anomaly_event.notification_status`가 `SENT`로 바뀌었는지 확인

## ML Studio 쪽에서 넣어줘야 하는 최소 컬럼

```text
equipment_id
window_end_time
anomaly_type
severity
metric_name
metric_value
threshold_value
anomaly_score
rule_score
iforest_score
final_score
duration_minutes
detection_window
message
notification_status='PENDING'
```

## severity 규칙

```text
normal   : 알림 없음
watch    : DB 기록만 권장
warning  : Teams 알림
critical : Teams 알림
recovery : 복구 알림
```
