# Redmine Handler Notifier

Redmine의 Open 이슈를 현재 담당자(Handler) 중심으로 정리해 Microsoft Teams로 전달하는 자동화입니다.

## 핵심 기능

- 평일 일일 알림: 마지막 성공 시점 이후 변경된 Open 이슈 요약
- 월요일 주간 알림: 전체 Open 이슈를 Handler별로 그룹화
- 담당자 미지정 및 14일/30일 이상 장기 미변경 이슈 강조
- 전체 페이지 조회로 기존 100/150건 제한 제거
- `.env` 기반 비밀정보 분리와 API 키 헤더 전송
- 네트워크 재시도, 요청 제한시간, 실패 종료 코드, 로테이션 로그
- Teams 메시지 크기에 따른 자동 분할
- 마지막 성공 시점과 전송 항목 기록으로 누락·중복 완화
- 프로젝트 미착수 기간에는 조회와 전송을 모두 건너뛰는 ON/OFF 제어

## 설정

```powershell
Copy-Item .env.example .env
```

`.env`에 Redmine 주소, 프로젝트 ID, API 키와 Power Automate/Teams Webhook URL을 입력합니다. `.env`는 Git에서 제외됩니다.

## 알림 ON/OFF

기본 상태는 **OFF**입니다. 작업 스케줄러는 유지되지만 OFF 상태에서는 Redmine 조회와 Teams 전송이 실행되지 않습니다.

```powershell
# 프로젝트 착수 시
powershell -ExecutionPolicy Bypass -File scripts\set_notification_state.ps1 -State On

# 프로젝트 중단 또는 종료 시
powershell -ExecutionPolicy Bypass -File scripts\set_notification_state.ps1 -State Off

# 현재 상태 확인
powershell -ExecutionPolicy Bypass -File scripts\set_notification_state.ps1 -State Status
```

## 실행

```powershell
python redmine_notifier.py daily --dry-run
python redmine_notifier.py weekly --dry-run
python redmine_notifier.py daily
python redmine_notifier.py weekly
```

## Windows 작업 스케줄러

기존 작업을 XML로 백업한 뒤 평일 10시 일일 작업과 월요일 13시 30분 주간 작업을 등록합니다.

```powershell
powershell -ExecutionPolicy Bypass -File scripts\install_scheduled_tasks.ps1
```

## 테스트

```powershell
python -m unittest discover -s tests -v
python -m compileall redmine_notifier.py redmine.py RedmineWeek.py redmineOpenNotice.py
```

## 보안

- `.env`, 로그, 런타임 상태와 기존 로컬 메일러 설정은 저장소에 포함하지 않습니다.
- 로그에는 API 키나 Webhook URL을 출력하지 않습니다.
- 공개 저장소에 커밋하기 전 비밀정보 스캔 결과를 확인합니다.

## AI 에이전트 Context 관리 (Akela)

이 프로젝트는 [Akela](https://github.com/TimothyHan/akela)를 사용해 Codex/Claude Code 같은 AI 에이전트가 작업할 때 전체 문서를 다 읽는 대신 필요한 지식만 골라 압축된 컨텍스트로 제공받습니다. 런타임 의존성이 아니며 실행/배포 동작에는 전혀 영향을 주지 않습니다.

- Knowledge: `knowledge/`
- Protocol: `akela/PROTOCOL.md`
- 설정: `akela.json`

작업 종류(activity)별로 관련 지식만 컴파일해서 사용하므로 매 작업마다 전체 문서를 컨텍스트에 넣을 때보다 토큰 사용량이 크게 줄어듭니다. 기본 흐름:

knowledge/ → `akela compile` → 작업별 slice.md → Codex/Claude 작업 → `akela log`로 Evidence 기록 → `akela stats`/curate로 지식 유지보수
