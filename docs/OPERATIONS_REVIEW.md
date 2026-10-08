# 자동실행 점검과 서버 이전 방향

확인일: 2026-10-08. 현재 대상 프로젝트와 Teams 채널을 유지하고 서버에서 ON 운영한다는 사용자 답변을 받았다.

## 최초 점검 당시 상태

- 이 하위 프로젝트의 origin은 https://github.com/hongmin3/redmine-handler-notifier.git 이다.
- Notion 「담당자 중심의 이슈 관리 체계 개정 및 알림 자동화」의 8절이 이 저장소의 알림 프로그램을 설명한다. 전체 Handler 운영 절차는 사람이 수행하며 이 코드가 담당자 변경을 자동 수행하지는 않는다.
- PC 일일 작업은 평일 10:00, 주간 작업은 월요일 13:30이다. 두 작업 모두 로그인한 사용자로 Python 프로그램을 실행한다.
- 10월 8일 일일 작업 종료 코드는 0이지만 같은 실행 시각의 로그는 알림 OFF로 조회와 전송을 건너뛰었다고 기록한다. 제어 파일의 enabled도 false다.
- 공용서버 ubuntu@10.13.0.222에 SSH 접속했다. Linux, Python 3.12.3이며 QA 서비스, 메뉴봇, AI Remote Hub가 실행 중이다.
- 확인한 systemd 시스템/사용자 작업 목록, ubuntu crontab, /opt와 /home/ubuntu의 깊이 2 이하 폴더에서 Redmine 배포를 찾지 못했다. 이 범위 밖의 배포는 확인하지 않았다.
- 서버 시간대는 America/New_York다. 기존 서비스 때문에 서버 전체 시간대를 바꾸지 않고 이 알림 일정에 Asia/Seoul을 지정한다.

## 발견한 문제

1. 기존 OFF는 Notion에 기록된 프로젝트 착수 전 운영 방침에 따른 상태다. 스케줄러의 종료 코드 0은 알림 전송 성공을 뜻하지 않는다.
2. ON 제어 파일이 UTF-8 BOM을 포함하면 load_json이 읽지 못해 OFF로 처리한다. 임시 파일의 enabled=true로 재현했다. Windows PowerShell 5.1의 Set-Content -Encoding UTF8과 연결되는 문제다.
3. split_blocks는 제한보다 긴 블록을 잘라낸다. 길이 11인 블록과 제한 10으로 원문 손실을 재현했다. 담당자 한 명의 주간 목록이 길면 일부 이슈가 메시지에서 빠질 수 있다.
4. 기존 SPEC은 기본 OFF, 성공 시각 기준 조회, 간단한 블록 분할만 정의한다. 전체 조회·전송·복구·서버 자동실행의 사양과 테스트 연결을 보완해야 한다.

```text
SPEC / CODE MISMATCH

Requirement: REQ-CORE-001 관련 ON 제어 동작
Specification: 제어 파일의 enabled=true는 활성화로 해석한다.
Current Implementation: UTF-8 BOM 파일은 JSON 읽기에 실패하여 OFF로 처리한다.
Difference: Windows에서 생성한 정상 ON 파일이 적용되지 않을 수 있다.
Action: CODE 수정 및 실제 PowerShell 생성 파일을 이용한 회귀 검증
```

## 구현 방향

1. 현재 요구사항을 유지하면서 BOM 읽기와 긴 목록의 원문 보존을 회귀 테스트로 재현하고 수정한다. 긴 목록 보존 계약을 SPEC에 추가한다.
2. 조회, 일일 중복 제외, 주간 Grade 제외, Teams 응답 처리, 실패 재시도, 성공 시각 저장, 서버 예약 실행을 SPEC의 요구사항과 테스트에 연결한다.
3. 공용서버의 독립 폴더와 가상환경에 배포한다. 기존 서비스나 서버 전체 설정을 변경하지 않는다. 비밀 설정은 내용을 출력하지 않고 별도 경로로 전달하며 기존 서버 파일은 덮어쓰지 않는다.
4. 시스템 systemd 서비스와 일일/주간 timer로 실행한다. 평일 10:00, 월요일 13:30 Asia/Seoul을 지정한다. 두 모드가 같은 잠금을 사용하도록 하며 실행 제한 30분과 실패 시 15분 간격 최대 3회 재시도를 유지한다. 잠금으로 건너뛴 실행은 전송 성공으로 기록하지 않는다.
5. 기존 대상 그대로 ON을 적용한다. 서버에서 실제 Redmine 조회와 일일/주간 메시지 생성을 확인한다. Teams 전송 후 채널 수신까지 확인하고 예약 실행 기록을 별도로 확인한다.
6. PC의 두 작업을 XML로 백업한 뒤 중지·비활성화하고 상태를 다시 읽는다. 작업 정의는 복구를 위해 남긴다.
7. 관련 테스트와 준비 검사 후 문서를 갱신하고 커밋·푸시한다. 재부팅 후 자동실행은 별도 검증 결과로 보고한다.

## 최초 점검 당시 막힌 단계

- PC의 일일 작업 XML 백업을 생성하고 읽어서 검증했다. Disable-ScheduledTask는 액세스 거부로 실패했다. 두 작업은 다시 읽었을 때 모두 Ready/Enabled=true였다. PC 중지 완료가 아니다.
- 서버 sudo -n은 비밀번호가 필요하다는 응답으로 실패했다. 사용자 서비스는 실행 중이지만 Linger=no여서 로그인과 무관한 상시 실행 수단으로 채택하지 않았다.
- PC 관리자 권한과 서버 systemd 등록 권한이 필요하다. 비밀번호를 채팅에 적지 않는다. 권한을 마련한 뒤 위 순서로 진행한다.
- 제품 코드, .env, config.ini, 알림 제어값은 이번 점검에서 수정하지 않았다. 서버 배포·ON 전환·Teams 전송은 아직 수행하지 않았다.

## 최초 점검 검증 범위

- python -m unittest discover -s tests -v: 기존 6건 통과. BOM·긴 블록·API·Teams·서버 일정의 검증을 대신하지 않는다.
- node .project-check/project-readiness.js .: 오류 0, 미확정 사항과 개요 그림 관련 경고 2건. 운영 완료를 뜻하지 않는다.
- 실제 PC 실행 로그, 예약 작업 설정, 제어 상태, 서버 접속과 서비스 상태를 읽었다. 새로운 실제 전송은 수행하지 않았다.

## 출처

- https://github.com/hongmin3/redmine-handler-notifier
- https://app.notion.com/p/38f66f6ab3cd805e9b04c5413d7b856e?source=copy_link
- redmine_notifier.py, scripts/install_scheduled_tasks.ps1, scripts/set_notification_state.ps1, tests/test_redmine_notifier.py

## 적용 결과와 운영 방법

최초 점검 이후 관리자 권한으로 PC 작업 두 개를 XML 백업하고 비활성화했다. 서버는 시스템 systemd 서비스로 운영하며 사용자 로그인에 의존하지 않는다. 설치된 서비스를 통한 전송과 Teams 채널 수신 결과는 progress.md에 기록했다.

서버 이름 해석 실패는 hosts의 해당 Redmine 이름 항목 추가로 해결했다. 기존 hosts 파일은 백업했다. 기존 Webhook의 HTTP 401은 사용자가 승인한 같은 채널의 새 Teams 흐름으로 해결했다. 원래 .env는 수정하지 않았다.

### 상태 확인

서버 배포 폴더에서 다음 명령을 사용한다.

```sh
.venv/bin/python scripts/set_notification_state.py status
systemctl list-timers 'redmine-notifier-*'
systemctl show redmine-notifier@daily.service redmine-notifier@weekly.service -p Result -p ExecMainStatus
journalctl -u redmine-notifier@daily.service -u redmine-notifier@weekly.service --since today
```

ON/OFF 변경은 `scripts/set_notification_state.py on` 또는 `--state off`로 한다. 실행 기록은 logs, 성공 상태와 비밀 Webhook은 runtime에 있다. Webhook 보호 파일을 터미널에 출력하지 않는다.

### 복구

서버 예약을 중지할 때는 관리자 권한으로 두 timer를 disable --now 한다. PC 예약을 다시 켜야 한다면 서버 중지를 먼저 확인하고 scheduler-backup의 XML과 실행 경로를 확인한다. 양쪽 예약을 동시에 활성화하면 중복 알림이 발생할 수 있다.

서버 설치기는 이전 유닛을 scheduler-backup에 백업한다. 배포 갱신기는 이전 Python 진입점을 별도로 보관한다. 서버 hosts 복원은 다른 프로젝트의 이후 변경과 대조한 뒤 해당 항목만 되돌린다.

재부팅 시험과 다음 예약 시각에서의 자동 실행은 아직 확인하지 않았다. 예약 활성 상태와 수동 서비스 시작 성공을 해당 시험의 완료로 취급하지 않는다.
