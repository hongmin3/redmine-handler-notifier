# Troubleshooting

## 알림이 아예 오지 않음
<!-- akela: id=no-notification scope=notification-failure tier=must -->

1. `scripts\set_notification_state.ps1 -State Status`로 ON/OFF 확인 — 기본값이 OFF이므로 프로젝트 착수 후 On으로 바꾸지 않았을 가능성이 가장 높다.
2. `logs\redmine_notifier.log`에서 마지막 실행 로그 확인. "Notifications are OFF", "No matching issues. Notification skipped." 등은 정상 동작이며 오류가 아니다.
3. Windows 작업 스케줄러에서 "Redmine 24시간 알림 자동화"/"레드마인 오픈 이슈 알림" 작업의 마지막 실행 결과(Last Run Result)와 다음 실행 시각을 확인한다.
4. `python redmine_notifier.py daily --dry-run`을 수동 실행해 예외 발생 여부와 로그 출력을 확인한다.

## Redmine API 인증/조회 실패
<!-- akela: id=redmine-api-failure scope=notification-failure tier=must -->

- `RuntimeError: Required environment variable is missing: REDMINE_BASE_URL/REDMINE_PROJECT_ID/REDMINE_API_KEY` — `.env`에 값이 없거나 `.env` 파일 자체가 로드되지 않은 경우. `.env`가 프로젝트 루트에 있는지, 스케줄러의 WorkingDirectory가 올바른지 확인한다.
- Redmine 응답이 401/403이면 API 키가 만료/변경됐거나 해당 프로젝트에 대한 권한이 없는 것이다. Redmine 계정 설정에서 API 키를 재확인한다.
- `verify_tls` 관련 SSL 오류는 이 알림 경로(`redmine_notifier.py`)에는 없는 옵션이며, requests 기본 검증을 사용한다. 사내망 인증서 문제라면 `REDMINE_BASE_URL`이 http/https 중 올바른 스킴인지부터 확인한다.
- 429/500/502/503/504는 `Retry`(최대 3회, backoff)로 자동 재시도되므로, 재시도 후에도 실패하면 Redmine 서버 자체 점검이 필요하다.

## Teams(Power Automate) 전송 실패
<!-- akela: id=teams-webhook-failure scope=notification-failure tier=must -->

- `RuntimeError: Teams webhook failed with HTTP {code}` — Webhook URL 만료/변경, Power Automate 플로우 비활성화, 또는 페이로드 형식 문제일 수 있다. `TEAMS_WEBHOOK_URL`이 유효한지, 연결된 Power Automate 플로우가 여전히 켜져 있는지 확인한다.
- `RuntimeError: Required environment variable is missing: TEAMS_WEBHOOK_URL` — 전송할 이슈는 있는데 Webhook URL이 비어 있는 경우. `.env` 설정 누락.
- 메시지가 너무 길어 잘리거나 여러 개로 쪼개지는 것은 `TEAMS_MAX_CHARS` 기준 자동 분할이며 정상 동작이다. 분할 카드 순서가 이상하면 `(page/total)` 표기를 확인한다.

## 중복 알림 / 알림 누락 (일간)
<!-- akela: id=daily-duplicate-missing scope=notification-failure tier=should -->

- 같은 이슈가 반복 알림되면 `runtime/state.json`의 `daily_seen` 키(`이슈ID:updated_on`)가 갱신되지 않은 것 — 실행 중 예외로 `save_json`까지 도달하지 못했을 가능성이 있다. 로그에서 해당 실행이 끝까지 완료됐는지 확인한다.
- 이슈가 누락되면(예: 주말 사이 변경분) `daily_since` 계산 로직(월요일 72시간, 평일 24시간, 최대 7일 lookback) 범위를 벗어났을 수 있다. `--lookback-hours`로 넓은 범위를 수동 재조회해 복구한다.

## 일반 점검 순서 (확실치 않을 때)
<!-- akela: id=general-checklist scope=all tier=should -->

1. 로그(`logs/`) 최근 항목 확인
2. `.env` 값 존재 여부만 확인(내용은 열람 금지) — 값이 비어있는 항목이 있는지
3. 알림 ON/OFF 상태 확인
4. 수동 `--dry-run` 실행으로 재현
5. 네트워크(Redmine 서버, Teams Webhook 엔드포인트) 접근 가능 여부 확인
6. 그래도 원인 불명이면 Redmine 서버/Power Automate 측 변경 이력을 문의
