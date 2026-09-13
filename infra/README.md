# Infrastructure as Code

이 디렉터리는 스마트 팩토리 전력 관제 파이프라인의 Azure 기반 공통 인프라를 Bicep으로 관리합니다. 리소스 그룹 단위 배포를 기준으로 하며, 배포는 Incremental 모드로 수행합니다.

## 구성

- main.bicep: 전체 리소스 조합과 환경별 입력 정의
- modules/storage.bicep: Function 런타임용 Storage Account
- modules/monitoring.bicep: Log Analytics Workspace와 Application Insights
- modules/key-vault.bicep: RBAC 기반 Key Vault
- modules/event-hubs.bicep: 전력 원천 이벤트와 이상 이벤트용 Event Hubs
- modules/function-app.bicep: Python 3.11 Linux Function Apps, Managed Identity, Storage RBAC
- modules/sql.bicep: 선택적으로 생성하는 Azure SQL Server와 Database
- environments/dev.bicepparam: 개발 환경 입력
- environments/prod.bicepparam: 운영 환경 입력

Function App은 다음 파이프라인 역할을 기준으로 생성됩니다.

- stream-producer: 5초 전력 이벤트 생산
- mlforecast: 수요 예측과 분석 처리
- anomaly: 이상 탐지 처리
- daily-report: 일일 리포트 생성
- alert-dispatcher: 이상 이벤트 알림 전송

## 보안 설계

- 저장소에는 비밀번호, 연결 문자열, 토큰을 넣지 않습니다.
- Key Vault는 RBAC 권한 모델과 purge protection을 사용합니다.
- Function App은 System Assigned Managed Identity를 사용하고 Storage 데이터 권한을 RBAC으로 부여합니다.
- Event Hubs 데이터 수신 권한도 Managed Identity에 부여합니다.
- SQL 모듈은 서버명과 데이터베이스명을 입력했을 때만 생성됩니다. 기본 dev/prod 파라미터는 SQL 생성을 건너뜁니다.
- SQL 모듈을 활성화할 때 비밀번호는 명령행 또는 배포 파이프라인의 secure parameter로 전달해야 합니다.
- SQL은 public network를 비활성화하므로, 운영 적용 전 Private Endpoint 또는 기존 SQL 네트워크 연결을 함께 결정해야 합니다.

## 로컬 검증

Azure CLI와 Bicep CLI가 설치된 환경에서 다음 명령으로 템플릿을 빌드합니다.

    az bicep build --file infra/main.bicep --outfile /tmp/smartfactory-main.json

실제 리소스 변경 전에는 what-if을 실행합니다.

    az deployment group what-if --resource-group <resource-group> --template-file infra/main.bicep --parameters infra/environments/dev.bicepparam

실제 배포에는 GitHub Actions의 Infrastructure what-if 결과를 확인한 뒤 Deploy infrastructure to dev workflow를 사용합니다. GitHub Environment에는 AZURE_CLIENT_ID, AZURE_TENANT_ID, AZURE_SUBSCRIPTION_ID Secret과 AZURE_RESOURCE_GROUP Variable을 등록해야 합니다.

애플리케이션 소스 배포는 인프라 배포와 분리합니다. IaC가 Function App과 의존 리소스를 준비한 뒤 각 Function 프로젝트의 배포 파이프라인을 연결합니다.
