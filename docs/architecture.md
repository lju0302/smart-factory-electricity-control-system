# 아키텍처

## 목적

이 문서는 저장소의 서비스 경계와 운영 데이터 흐름을 설명합니다. Azure 리소스 이름과 배포 변수는 `infra/`와 [운영 문서](operations.md)를 기준으로 확인합니다.

## 런타임 흐름

1. `fastapi/`가 DuckDB 또는 샘플 데이터에서 전력 이벤트를 읽습니다.
2. Stream Producer가 Event Hubs `power-events`로 원천 이벤트를 전송합니다.
3. Azure Stream Analytics가 `localtime_datetime` 기준으로 1분·15분 윈도우를 계산합니다.
4. 1분 결과는 SQL `poweroutput`, 15분 결과는 `poweroutput_15m`에 저장됩니다.
5. ML 입력용 집계 이벤트는 `aggregated-power-data`로 전달됩니다.
6. SQL Timer Function이 `usp_timer_aggregate_1h`, `usp_timer_aggregate_1d`를 호출합니다.
7. 이상 탐지, 수요 예측, 리포트, 알림 Function이 각 결과를 소비합니다.

## 주요 이벤트 경계

| 경계 | 기본 이름 | 생산자 | 소비자 |
| --- | --- | --- | --- |
| 원천 이벤트 | `power-events` | FastAPI Stream Producer | Stream Analytics |
| 집계 이벤트 | `aggregated-power-data` | Stream Analytics | anomaly/forecast 파이프라인 |
| 이상 이벤트 | `anomaly-events` | 이상 탐지 결과 | Alert Function |

이름은 환경별 Bicep parameter로 바꿀 수 있으며, 소스의 기본값과 실제 배포값이 다를 경우 배포 parameter를 우선합니다.

## 서비스 책임

### FastAPI Stream Producer

원천 이벤트 생성과 전송 제어를 담당합니다. API는 스트림 실행 상태를 보여주며, 설비 제어 명령을 수행하지 않습니다.

### Stream Analytics

5초 이벤트를 운영 조회에 필요한 1분·15분 집계로 변환합니다. 윈도우 집계와 Event Hubs/SQL 출력의 연결은 `infra/queries/stream-analytics-aggregation.sql`에서 관리합니다.

### SQL Timer Function과 저장 프로시저

Timer Function은 스케줄링 경계만 담당하고, 1시간·1일 집계 규칙은 SQL 저장 프로시저에 둡니다. 재실행 시 중복을 만들지 않도록 프로시저의 대상 구간과 upsert 기준을 함께 검토해야 합니다.

### 이상 탐지

`ml_package/score.py`가 1분·15분·1시간·1일 입력을 지원합니다. 데이터 품질을 먼저 확인한 뒤 Rule/IQR와 Isolation Forest 결과를 조합해 점수·등급·권고를 생성합니다.

### 예측

`mlforecast/`는 SQL 집계 데이터를 입력으로 NHITS/TFT 추론을 수행하고 예측 결과를 저장합니다. 모델 파일과 학습 산출물은 공개 저장소에 포함하지 않습니다.

### 알림

이상 결과는 `anomaly_event`에 대기 상태로 기록되고, Alert Function이 대기 이벤트를 읽어 Power Automate 또는 Teams/Email 알림으로 전달합니다. 알림 전송은 설비 제어와 분리되어 있습니다.

## 저장 계층

| 계층 | 대표 데이터 | 목적 |
| --- | --- | --- |
| 원천 | Event Hubs `power-events` | 5초 전력 이벤트 수집 |
| 운영 집계 | `poweroutput`, `poweroutput_15m` | 모니터링과 분석 입력 |
| 장기 집계 | 1시간·1일 SQL 집계 | 리포트·추세 분석 |
| 분석 결과 | anomaly/forecast 테이블 | 운영 판단과 알림 |

## 변경 영향 점검

다음 변경은 관련 소비자를 함께 확인해야 합니다.

- Event Hubs payload 필드·단위·타임존 변경
- 집계 윈도우, 그룹 키, null 처리 변경
- SQL 저장 프로시저의 대상 구간 또는 상태값 변경
- `anomaly_event` 상태 전이·중복 방지 기준 변경
- 예측 입력 컬럼 또는 모델 artifact 경로 변경

계약 변경은 코드와 문서를 같은 PR에 포함하고, 기존 이벤트를 재처리할 때의 호환성을 기록합니다.
