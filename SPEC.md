# Redmine Handler Notifier 사양서

<!-- spec-template: v1 -->

| 항목 | 값 |
|---|---|
| Document Version | 0.2.0 |
| Last Updated | 2026-10-08 |
| Status | implemented |

기존 알림 계약을 유지하면서 공용서버 자동실행을 추가한다. 2026-10-08 사용자가 현재 프로젝트와 Teams 채널 그대로 서버 ON 운영을 요청했다. 전송 요청 접수, 채널 수신, 예약 실행은 각각 확인한다.

## 1. 목적

Open 이슈를 담당자별로 정리해 알림으로 전달한다.

### 한눈에 보기

```flow
예약 시각 -> ON 확인 -> Redmine 조회 -> 목록 정리 -> Teams 전송 -> 성공 기록
ON 확인 -(OFF)-> 건너뜀 기록
Redmine 조회 -(실패)-> 실패 기록 -> 예약 재시도
Teams 전송 -(실패)-> 실패 기록 -> 예약 재시도
```

| 용어 | 뜻 |
|---|---|
| Handler | 현재 이슈를 다음 단계로 진행할 담당자 |
| BOM | 일부 Windows 프로그램이 UTF-8 파일 앞에 붙이는 표시 |
| systemd | Linux의 서비스·예약 실행 관리자 |

## 2. 프로젝트 범위

포함: 일일 변경 알림, 주간 담당자별 목록, ON/OFF, 전체 페이지 조회, Teams 전송, 공용서버 자동실행과 PC 예약 작업 중지.

제외: Redmine의 담당자·상태 자동 변경과 별도 메일러. 비밀 설정은 출력하지 않으며 배포 시 파일 그대로 전달한다. 기존 성공 기록은 보존한다.

## 4. 실행 구성

| 작업 | 시각·시간대 | 위치·조건 | 기록·알림 |
|---|---|---|---|
| 일일 | 평일 10:00 Asia/Seoul | 공용 Linux 서버, ON | runtime 성공 상태·logs, Teams |
| 주간 | 월요일 13:30 Asia/Seoul | 공용 Linux 서버, ON | logs, Teams |

## 5. 기능 요구사항

| 카테고리 | 이름 |
|---|---|
| CORE | 알림 제어와 메시지 구성 |
| QUERY | 전체 이슈 조회 |
| DAILY | 일일 알림 |
| WEEKLY | 주간 알림 |
| DELIVERY | Teams 전송 |
| OPS | 서버 자동실행과 PC 중지 |
| SECURITY | 비밀정보와 운영 기록 보호 |

### REQ-CORE-001 기본 OFF

환경변수 지정이 없고 알림 제어 파일도 없으면 notifications_enabled는 거짓을 반환한다. 제어 파일의 enabled=true는 BOM 유무와 관계없이 활성화로 해석한다. 손상된 파일은 OFF로 처리한다.

NOTIFICATIONS_ENABLED 환경변수가 제어 파일보다 우선한다. OFF면 조회와 전송을 건너뛰고 로그를 남긴다.


### REQ-CORE-002 성공 시점 overlap

별도 조회 기간 지정 없이 2시간 전 성공시각이 있으면 daily_since는 마지막 성공시각에서 5분을 뺀 시각을 반환한다. 조회 시작은 최대 7일 전까지로 제한한다. 성공 기록이 없으면 월요일은 72시간, 다른 요일은 24시간 전부터 조회한다.


### REQ-CORE-003 블록 분할

메시지 블록을 합칠 때 길이 제한을 넘는다면 별도 메시지로 분리한다. 길이 8인 두 블록과 제한 10의 입력은 두 블록을 각각 보존해 반환한다.

블록 하나가 제한보다 길어도 뒷부분을 버리지 않는다. 줄 경계에서 우선 나누며 긴 한 줄도 모든 문자를 보존한다. 제한은 1 이상의 정수여야 한다.


### REQ-QUERY-001 전체 Open 조회

Redmine API에 Open 조건을 전달하고 total_count와 offset으로 모든 페이지를 조회한다. API 키는 헤더에 넣는다. 제한시간을 지정하고 GET 연결·응답 실패와 HTTP 429/500/502/503/504는 최대 3회 재시도한다.

### REQ-DAILY-001 변경 알림과 성공 기록

이슈 번호와 수정 시각이 이전 전송 기록에 있는 항목은 제외한다. 번호·제목·상태·Handler·Grade·수정일·링크를 알린다. 모든 전송이 성공하면 성공 시각과 전송 항목을 저장한다. 대상이 없어도 조회가 성공하면 시각을 저장한다.

드라이런과 실패는 성공 상태를 갱신하지 않는다. --lookback-hours는 조회 기간을 지정한다.

### REQ-WEEKLY-001 담당자별 목록

전체 Open 이슈를 Handler별로 정리하며 제외 Grade 기본값은 D다. 담당자 미지정을 먼저 표시하고 14일 이상·30일 이상 미변경을 구분한다. 보류 항목은 그룹 안에서 뒤에 둔다.

### REQ-DELIVERY-001 Teams 전송 결과

Adaptive Card를 Power Automate/Teams Webhook으로 전달한다. HTTP 200/202는 요청 접수 성공으로 처리한다. 다른 응답과 요청 실패는 비정상 종료 코드와 로그를 남긴다.

> **주의** 요청 접수와 Teams 수신은 별도 확인한다. 여러 메시지 중 일부를 전송하고 실패하면 재시도에서 중복될 수 있다.

### REQ-OPS-001 공용서버 자동실행

독립 폴더·가상환경에서 평일 10:00 일일, 월요일 13:30 주간 작업을 실행한다. 일정은 Asia/Seoul이며 로그인 없이 서버 부팅 후에도 예약된다. 놓친 일정은 부팅 후 실행한다. 서버 전체 시간대와 다른 서비스는 변경하지 않는다.

실패 시 15분 간격으로 최초 실행 외 최대 3회 재시도한다. 시도당 제한은 30분이다. 일일·주간 작업은 같은 잠금을 사용한다. 잠금 충돌은 실패로 기록하고 재시도한다.

### REQ-OPS-002 PC 예약 작업 중지

현재 프로젝트의 두 작업만 XML 백업 후 중지·비활성화한다. 실행 경로와 인수가 이 프로젝트와 맞는지 확인한다. 권한이 없으면 실패로 보고한다. 복구를 위해 작업 정의를 남긴다.

## 8. 비기능 요구사항

### NFR-SECURITY-001 비밀정보와 운영 기록 보호

.env/config.ini는 출력하거나 Git에 넣지 않는다. 배포에 필요한 .env는 파일 그대로 전달하고 서버 소유자만 읽게 한다. 새 Webhook은 표준 입력으로 받아 runtime/teams-webhook.env에 소유자만 읽도록 저장한다. 이 파일은 서비스 환경변수로 적용한다. 기존 성공 기록을 초기화하지 않는다. API 키와 Webhook URL을 로그에 넣지 않는다. 로그는 1MB 단위로 이전 파일 5개를 보관한다.

## 9. 오류 처리 정책

OFF와 조회 대상 없음은 정상 종료다. 조회·전송 실패는 종료 코드 1이다. 실패와 드라이런을 성공 기록으로 저장하지 않는다.

## 11. 테스트 사양

운영 .env/config.ini/runtime은 읽지 않는다. 제어 파일 fixture는 TemporaryDirectory 안에 생성한다. 환경변수 NOTIFICATIONS_ENABLED가 테스트 기본값 판정에 간섭하지 않는 격리 환경을 사용한다.

개발 의존성을 준비하고 프로젝트 루트에서 실행할 명령:

```text
python -m unittest discover -s tests -v
```

실제 CLI 테스트는 프로그램을 임시 폴더에 복사하고 로컬 HTTP 서버로 조회·전송·실패·중복 제외를 확인한다. 운영 비밀 설정은 읽지 않는다.

### TEST-CORE-001

REQ-CORE-001의 입력과 결과를 `tests/test_redmine_notifier.py`의 `test_notifications_default_to_off` fixture/assertion으로 검증한다. 해당 assertion 실패는 검사 실패다.

### TEST-CORE-002

REQ-CORE-002의 입력과 결과를 `tests/test_redmine_notifier.py`의 `test_daily_since_uses_previous_success_with_overlap` fixture/assertion으로 검증한다. 해당 assertion 실패는 검사 실패다.

### TEST-CORE-003

REQ-CORE-003의 입력과 결과를 `tests/test_redmine_notifier.py`의 `test_split_blocks_respects_limit` fixture/assertion으로 검증한다. 해당 assertion 실패는 검사 실패다.

### TEST-OPS-001 서버 일정과 실행

서버에서 systemd-analyze verify로 유닛 문법을 확인한다. systemd-analyze calendar로 한국 시간의 다음 일정을 확인한다. timer 활성 상태, 실제 서비스 종료 결과와 조회·전송 로그를 읽는다. 재부팅 후 확인은 별도로 기록한다.

### TEST-OPS-002 PC 중지 확인

관리자 권한으로 PC 중지 스크립트를 실행한다. 백업 XML 인수와 두 작업의 Enabled=false, 실행 프로세스 부재를 확인한다.

## 12. 요구사항 추적성

| Requirement | Implementation | Test | Status |
|---|---|---|---|
| REQ-CORE-001 | `redmine_notifier.py` | TEST-CORE-001: `tests/test_redmine_notifier.py` | implemented |
| REQ-CORE-002 | `redmine_notifier.py` | TEST-CORE-002: `tests/test_redmine_notifier.py` | implemented |
| REQ-CORE-003 | `redmine_notifier.py` | TEST-CORE-003: `tests/test_redmine_notifier.py` | implemented |
| REQ-QUERY-001 | `redmine_notifier.py` | `tests/test_cli.py` | implemented |
| REQ-DAILY-001 | `redmine_notifier.py` | `tests/test_cli.py` | implemented |
| REQ-WEEKLY-001 | `redmine_notifier.py` | `tests/test_redmine_notifier.py`, `tests/test_cli.py` | implemented |
| REQ-DELIVERY-001 | `redmine_notifier.py` | `tests/test_cli.py` | implemented |
| REQ-OPS-001 | `scripts/install_server.sh`, `scripts/run_scheduled.py`, `deploy/systemd/redmine-notifier@.service`, `deploy/systemd/redmine-notifier-daily.timer`, `deploy/systemd/redmine-notifier-weekly.timer` | `tests/test_scheduled_runner.py`, TEST-OPS-001 | implemented |
| REQ-OPS-002 | `scripts/disable_local_tasks.ps1` | TEST-OPS-002 | implemented |
| NFR-SECURITY-001 | `redmine_notifier.py`, `scripts/install_server.sh`, `scripts/set_server_webhook.py` | `tests/test_cli.py`, `tests/test_server_webhook.py`, TEST-OPS-001 | implemented |

implemented는 구현·테스트 소스 연결을 확인했다는 뜻이며 실제 실행 통과를 의미하지 않는다.

## 13. 미확정 사항

- 재부팅 후 자동실행과 다음 예약 실행 결과는 확인 필요다. 실제 전송·수신과 별도로 기록한다.
