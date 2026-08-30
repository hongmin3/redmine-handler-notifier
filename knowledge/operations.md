# Operations

## config.ini / .env 운영 방식
<!-- akela: id=config-operations scope=config-change tier=must -->

- `.env`는 `redmine_notifier.py` 계열(RedmineWeek.py, redmine.py, redmineOpenNotice.py가 내부적으로 호출하는 진입점)이 사용하는 설정으로, `REDMINE_BASE_URL`, `REDMINE_PROJECT_ID`, `REDMINE_API_KEY`, `TEAMS_WEBHOOK_URL`, `REDMINE_EXCLUDED_GRADES`, `HTTP_TIMEOUT_SECONDS`, `TEAMS_MAX_CHARS` 등을 정의한다. `.env.example`을 복사해 채우며 Git에서 제외된다.
- `config.ini`는 `redmine_activity_mailer.py` 전용 설정 파일(`[redmine]`, `[email]`, `[options]` 섹션)이며 Git에서 제외된다. 이 파일과 `.env`는 절대 열람·인용하지 않는다.
- 두 설정 체계는 서로 독립적이다. `.env`를 바꿔도 `redmine_activity_mailer.py`의 동작에는 영향이 없고, 그 반대도 마찬가지다.

## 알림 ON/OFF 제어
<!-- akela: id=notification-toggle scope=config-change tier=must -->

- `runtime/notification_control.json`에 `{"enabled": bool, "changed_at": ..., "changed_by": ...}` 형태로 저장되며, 기본값은 OFF다.
- `scripts/set_notification_state.ps1 -State On|Off|Status`로 제어한다. 프로젝트 착수 시 On, 중단/종료 시 Off로 전환하는 것이 표준 절차다.
- `NOTIFICATIONS_ENABLED` 환경변수가 설정돼 있으면 control 파일보다 우선한다(임시 override 용도로 추정).
- 작업 스케줄러 자체는 On/Off와 무관하게 항상 등록돼 있고, OFF 상태에서는 스크립트가 실행은 되지만 Redmine 조회와 Teams 전송만 스킵한다(로그에 "Notifications are OFF" 기록).

## Windows 작업 스케줄러 운영
<!-- akela: id=scheduler-ops scope=scheduler-recovery tier=must -->

- `scripts/install_scheduled_tasks.ps1`이 두 작업을 등록/갱신한다: "Redmine 24시간 알림 자동화"(평일 10:00, `redmine_notifier.py daily`), "레드마인 오픈 이슈 알림"(월요일 13:30, `redmine_notifier.py weekly`).
- 스크립트 실행 시 기존 동일 이름 작업이 있으면 먼저 `Export-ScheduledTask`로 XML을 `scheduler-backup/`에 타임스탬프(`{작업명}-yyyyMMdd-HHmmss.xml`)와 함께 백업한 뒤 `Register-ScheduledTask -Force`로 덮어쓴다. 즉 `scheduler-backup/`은 스케줄러 작업 정의의 이력/롤백용 백업 저장소다.
- 작업 설정은 `RestartCount 3`, `RestartInterval 15분`, `ExecutionTimeLimit 30분`, `MultipleInstances IgnoreNew`로 구성돼 있어 실패 시 자동 재시도되고 중복 실행은 무시된다.

## 재실행 / 복구 절차
<!-- akela: id=recovery-procedure scope=scheduler-recovery tier=must -->

- **수동 재실행**: `python redmine_notifier.py daily` 또는 `weekly`를 프로젝트 루트에서 직접 실행하면 스케줄러와 동일한 로직이 즉시 수행된다. `--dry-run`으로 전송 없이 확인 가능하고 `--preview-file <path>`로 생성될 Teams 페이로드를 JSON으로 저장해 검토할 수 있다(`preview-daily.json`, `preview-weekly.json`이 그 산출물).
- **누락 구간 재조회**: `--lookback-hours N`으로 `runtime/state.json`의 마지막 성공 시각과 무관하게 임의 시간 범위를 강제 조회할 수 있다(예: 스케줄러가 하루 멈췄다가 복구된 경우).
- **state 초기화가 필요한 경우**: `runtime/state.json`(daily_last_success_utc, daily_seen)을 직접 수정/삭제하면 다음 실행 시 재계산되지만, 이는 운영 산출물이므로 임의로 건드리지 않는다 — 필요 시 사람이 판단해 조작한다.
- **스케줄러 작업 자체가 깨졌을 때**: `scheduler-backup/`의 최신 XML을 `Register-ScheduledTask -Xml (Get-Content ... -Raw)`로 재등록하거나, `scripts/install_scheduled_tasks.ps1`을 다시 실행해 재생성한다.
- **알림이 계속 안 갈 때 1차 확인**: `scripts/set_notification_state.ps1 -State Status`로 ON/OFF부터 확인한다(OFF가 가장 흔한 원인).
