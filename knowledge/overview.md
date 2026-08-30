# Overview

## 프로젝트 목적
<!-- akela: id=purpose scope=all tier=should -->

Redmine 프로젝트의 Open 이슈를 담당자(Handler) 중심으로 정리해 Microsoft Teams(Power Automate Webhook)로 자동 전달하는 사내 알림 자동화다. 담당자 미지정 이슈와 14일/30일 이상 오래 갱신되지 않은 이슈를 강조해 방치되는 이슈를 줄이는 것이 핵심 목표다.

## 일간/주간 Teams 알림 흐름
<!-- akela: id=notification-flow scope=all tier=should -->

두 흐름 모두 `redmine_notifier.py`의 `run()` 함수 하나를 통해 실행되며, 최초에 `runtime/notification_control.json`(또는 `NOTIFICATIONS_ENABLED` 환경변수)로 알림 ON/OFF를 확인한다. OFF면 Redmine 조회와 Teams 전송을 모두 건너뛴다.

- **일간 (`daily`, 평일 10시)**
  1. `runtime/state.json`의 `daily_last_success_utc`를 기준으로 조회 시작 시점(`daily_since`)을 계산한다. 월요일에는 주말 공백을 메우기 위해 기본 72시간, 그 외 평일은 24시간을 기본 lookback으로 사용한다.
  2. Redmine REST API(`GET /projects/{project}/issues.json`, `status_id=open`, `updated_on>=...`)를 전량 페이지네이션으로 조회한다(기존 100/150건 제한 제거).
  3. `daily_seen` 목록(이슈ID:updated_on 조합)으로 이미 보낸 항목을 걸러내 중복 알림을 방지한다.
  4. 상태별로 정렬한 이슈 블록을 만들어 Teams Adaptive Card로 전송하고, 성공 시 `daily_last_success_utc`와 `daily_seen`을 갱신한다.
- **주간 (`weekly`, 월요일 13:30)**
  1. 전체 Open 이슈를 조회(lookback 없이 전체)한다.
  2. Grade가 제외 대상(`REDMINE_EXCLUDED_GRADES`, 기본값 `D`)이 아닌 이슈만 담당자(Handler)별로 그룹화한다.
  3. 각 그룹 내에서 보류 상태를 뒤로, 정체 기간(stale_days)이 긴 순으로 정렬하고 14일/30일 이상 배지를 붙인다.
  4. 담당자별 리스트를 Teams Adaptive Card로 전송한다(주간은 별도 state 갱신 없음).

두 경로 모두 Teams 페이로드가 `TEAMS_MAX_CHARS`(기본 16000자)를 넘으면 여러 카드로 자동 분할해 전송한다.

## 주요 모듈 역할
<!-- akela: id=modules scope=all tier=should -->

- **`redmine_notifier.py`** — 실제 로직이 담긴 핵심 모듈. Redmine API 클라이언트(`RedmineClient`), 일간/주간 그룹화·정렬·Teams 페이로드 생성, dotenv 로딩, 로깅(회전 로그), state/control 파일 입출력을 모두 포함한다. `daily`/`weekly` 서브커맨드와 `--dry-run`, `--lookback-hours`, `--preview-file` 옵션을 제공한다.
- **`redmine.py`** — 하위호환용 진입점. `redmine_notifier.main(["daily"])`를 호출만 한다.
- **`redmineOpenNotice.py`** — Deprecated 진입점. 역시 `redmine_notifier.main(["daily"])`를 호출한다. (구버전 스케줄러 작업이 참조할 수 있어 남겨둠)
- **`RedmineWeek.py`** — 하위호환용 진입점. `redmine_notifier.main(["weekly"])`를 호출만 한다.
- **`redmine_activity_mailer.py`** — 별개 계열의 레거시 로컬 메일러. Redmine Activity 페이지를 쿠키 기반으로 스크래핑(BeautifulSoup)해 이슈 상태/등급/원인 변경을 이메일(SMTP)로 발송한다. `config.ini`를 사용하며, 머신별 로그인 세션 쿠키를 코드 내부에 하드코딩하는 구조라 `.gitignore`에서 명시적으로 제외되어 있다. `redmine_notifier.py` 계열과는 독립적으로 동작하는 별도 산출물이며, 이 파일은 수정하지 않는다.

## 설정 파일 구분(참고)
<!-- akela: id=config-files scope=config-change tier=should -->

- `.env` — `redmine_notifier.py` 계열(REDMINE_BASE_URL, REDMINE_PROJECT_ID, REDMINE_API_KEY, TEAMS_WEBHOOK_URL 등)이 사용하는 비밀정보. Git 제외.
- `config.ini` — `redmine_activity_mailer.py` 전용 설정(SMTP 계정, activity URL 등). Git 제외 대상이며 절대 열람/인용하지 않는다.
