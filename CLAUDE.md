# CLAUDE

Follow `akela/PROTOCOL.md` for every task.

## Project Root 탐색 규칙

이 저장소는 여러 위치에서 열릴 수 있으므로, 시작 디렉터리에서 위로 올라가며 `akela.json`을 우선으로 찾고 없으면 `AGENTS.md`, `CLAUDE.md`, `.git`, `README.md` 중 가장 가까운 것을 프로젝트 루트로 간주한다. 하드코딩된 절대 경로에 의존하지 않는다. `scripts/find-project-root.ps1 -StartPath <경로>`로 동일한 규칙을 스크립트로도 실행할 수 있다.

## 운영 산출물 — 건드리지 않음

`activity_state.json`, `logs/`, `runtime/`, `scheduler-backup/` 등은 실행 중 자동 생성/갱신되는 운영 산출물이며 Akela Context Engineering 레이어 적용과 무관하다. Akela 관련 작업(knowledge, akela.json, akela/, AGENTS.md/CLAUDE.md 갱신 등)을 수행할 때 이 산출물들을 수정, 삭제, 커밋 대상에 포함하지 않는다. `.env`, `config.ini`도 비밀정보가 담겨 있으므로 열람·인용·수정하지 않는다. 소스 코드(`*.py`)도 별도 지시가 없는 한 수정하지 않는다.

## 참고

- Knowledge: `knowledge/`
- Protocol: `akela/PROTOCOL.md`
- 설정: `akela.json`
