# Redmine Handler Notifier 사양서

<!-- spec-template: v1 -->

| 항목 | 값 |
|---|---|
| Document Version | 0.1.0 |
| Last Updated | 2026-09-21 |
| Status | draft — 기존 계약 일부의 근거 기반 사양화 |

기존 코드와 테스트의 명시적 약속을 처음으로 연결한 제한된 기준선이다. 전체 제품 사양이나 운영 검증 완료를 뜻하지 않는다. 기존 약속과 구현의 차이는 SPEC / CODE MISMATCH로 남기고 코드에 맞춰 약속을 바꾸지 않는다.

## 1. 목적

Open 이슈를 담당자별로 정리해 알림으로 전달한다.

## 2. 프로젝트 범위

포함: 알림 기본 상태·일간 조회 시작점·메시지 분할.

제외: 운영 데이터·비밀 설정의 열람/변경, 기능 수정, 인증·배포·예약 실행 변경. 이 제외는 작업 경계이며 기존 제품 기능을 제거한다는 뜻이 아니다.

## 5. 기능 요구사항

### REQ-CORE-001 기본 OFF

명시적 환경변수 override가 없고 알림 제어 파일도 없으면 notifications_enabled는 거짓을 반환한다. 제어 파일의 enabled=true는 활성화로 해석한다.

관련 구현: `redmine_notifier.py`. 관련 테스트: `tests/test_redmine_notifier.py`의 `test_notifications_default_to_off`.

### REQ-CORE-002 성공 시점 overlap

별도 lookback override 없이 2시간 전 성공시각이 있으면 daily_since는 마지막 성공시각에서 5분을 뺀 시각을 반환한다.

관련 구현: `redmine_notifier.py`. 관련 테스트: `tests/test_redmine_notifier.py`의 `test_daily_since_uses_previous_success_with_overlap`.

### REQ-CORE-003 블록 분할

메시지 블록을 합칠 때 길이 제한을 넘는다면 별도 메시지로 분리한다. 길이 8인 두 블록과 제한 10의 입력은 두 블록을 각각 보존해 반환한다.

관련 구현: `redmine_notifier.py`. 관련 테스트: `tests/test_redmine_notifier.py`의 `test_split_blocks_respects_limit`.

## 9. 오류 처리 정책

알림 OFF는 정상적인 건너뜀 상태다. 실제 전송 실패와 성공 상태 기록은 이번 문서 작업에서 실행 검증하지 않는다. 기존 운영 state/control 및 예약 작업을 변경하지 않는다.

## 11. 테스트 사양

운영 .env/config.ini/runtime은 읽지 않는다. 제어 파일 fixture는 TemporaryDirectory 안에 생성한다. 환경변수 NOTIFICATIONS_ENABLED가 테스트 기본값 판정에 간섭하지 않는 격리 환경을 사용한다.

개발 의존성을 준비하고 프로젝트 루트에서 실행할 명령:

```text
python -m unittest discover -s tests -p test_redmine_notifier.py -v
```

이번 작업에서는 테스트 본문과 구현 연결을 확인했으며 명령을 실제 실행하지 않았다.

### TEST-CORE-001

REQ-CORE-001의 입력과 결과를 `tests/test_redmine_notifier.py`의 `test_notifications_default_to_off` fixture/assertion으로 검증한다. 해당 assertion 실패는 검사 실패다.

### TEST-CORE-002

REQ-CORE-002의 입력과 결과를 `tests/test_redmine_notifier.py`의 `test_daily_since_uses_previous_success_with_overlap` fixture/assertion으로 검증한다. 해당 assertion 실패는 검사 실패다.

### TEST-CORE-003

REQ-CORE-003의 입력과 결과를 `tests/test_redmine_notifier.py`의 `test_split_blocks_respects_limit` fixture/assertion으로 검증한다. 해당 assertion 실패는 검사 실패다.

## 12. 요구사항 추적성

| Requirement | Implementation | Test | Status |
|---|---|---|---|
| REQ-CORE-001 | `redmine_notifier.py` | TEST-CORE-001: `tests/test_redmine_notifier.py` | implemented |
| REQ-CORE-002 | `redmine_notifier.py` | TEST-CORE-002: `tests/test_redmine_notifier.py` | implemented |
| REQ-CORE-003 | `redmine_notifier.py` | TEST-CORE-003: `tests/test_redmine_notifier.py` | implemented |

implemented는 구현·테스트 소스 연결을 확인했다는 뜻이며 실제 실행 통과를 의미하지 않는다.

## 13. 미확정 사항

- 실제 API 페이지 조회·Teams 전송·재시도·상태 저장 전체의 추적성 및 예약 실행 결과는 확인 필요다.
- 미확정 범위 검토 전에는 전체 프로젝트 readiness 완료로 보고하지 않는다.
