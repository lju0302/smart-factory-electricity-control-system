# 데이터 파이프라인과 집계 기준

## 시간 단위별 책임

| 레벨 | 생성 방식 | 대표 테이블/출력 | 주요 사용처 |
| --- | --- | --- | --- |
| 5초 | 원천 이벤트 | `power-events` | 스트림 입력 |
| 1분 | Stream Analytics window | `poweroutput` | 운영 조회·기본 이상 탐지 |
| 15분 | Stream Analytics window | `poweroutput_15m` | 추세 분석·ML 입력 |
| 1시간 | `usp_timer_aggregate_1h` | 시간 집계 테이블 | 시간별 운영 분석 |
| 1일 | `usp_timer_aggregate_1d` | 일 집계 테이블 | 일일 리포트·장기 추세 |

## Stream Analytics

Stream Analytics는 원천 Event Hubs 입력 `powerinput`을 읽고 `localtime_datetime`을 기준으로 윈도우를 계산합니다. 쿼리와 출력 연결은 `infra/queries/stream-analytics-aggregation.sql`에서 관리합니다.

1분·15분 집계에는 설비 또는 장비를 식별할 수 있는 그룹 키와 전력 통계값이 포함되어야 합니다. 입력에 없는 값은 임의의 기본값으로 보정하지 않고 null 또는 품질 상태로 구분합니다.

## SQL Timer 집계

SQL Timer Function은 집계 실행 시점을 제공하고, 집계 로직은 다음 저장 프로시저에 둡니다.

- `usp_timer_aggregate_1h`
- `usp_timer_aggregate_1d`

프로시저를 수정할 때는 다음을 확인합니다.

- 처리 구간이 UTC와 로컬 시간 중 무엇을 기준으로 하는지
- 같은 구간을 다시 실행해도 중복 행이 생기지 않는지
- 늦게 도착한 이벤트를 재집계할 수 있는지
- 원천 데이터가 없는 구간을 0으로 만들지 null로 남길지
- 리포트와 예측 소비자가 기대하는 컬럼·단위가 유지되는지

## 분석 소비자

- `ml_package/`는 집계 레벨별 입력을 받아 품질 플래그와 이상 결과를 만듭니다.
- `mlforecast/`는 시간 집계 데이터를 받아 수요 예측 결과를 저장합니다.
- `functions/`는 일일 집계와 분석 결과를 바탕으로 운영 리포트를 만듭니다.
- `power-anomaly-alert-function/`은 `anomaly_event`의 대기 이벤트를 외부 알림 채널로 보냅니다.

## 데이터 품질

파이프라인 운영 시 다음 상태를 별도로 관찰합니다.

- 이벤트 지연 또는 누락
- 동일 이벤트의 중복
- 타임존·단위 불일치
- 설비 식별자 누락
- 집계 구간별 행 수와 통계값 급변
- 모델 입력 컬럼 누락

품질 이상은 분석 결과와 함께 기록하고, 자동 제어 판단의 근거로 사용하지 않습니다.

## 계약 변경 규칙

이벤트나 테이블 컬럼을 추가·변경할 때는 생산자, Stream Analytics 쿼리, SQL 저장 프로시저, ML 입력, 리포트, 알림 소비자를 함께 검색합니다. 필드 삭제·이름 변경·단위 변경은 호환 기간과 마이그레이션 방법을 PR에 기록합니다.
