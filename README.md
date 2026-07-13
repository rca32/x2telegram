# x2telegram

`x2telegram`은 X 타임라인을 제한된 범위로 읽고, 새 트윗만 digest로 요약해 Telegram으로 보내는 재사용 가능한 Python 패키지입니다.

현재 기본 구성은 다음과 같습니다.

- Source: 로컬 `bird` CLI의 home/following timeline
- Summarizer: `codex exec` 또는 Claude Code print mode를 호출하는 coding-agent adapter
- Sender: Telegram Bot API `sendMessage`
- State: 성공적으로 전송한 tweet id를 JSON에 저장하는 dedupe store

직접 LLM API를 연동하지 않고 이미 로그인된 coding-agent CLI를 비대화형으로 재사용합니다. 요약기는 새 트윗 JSON만 전달받으며 X/Telegram 인증값이나 프로젝트 파일에는 접근하지 않습니다. API 호출 없는 규칙 기반 `digest` provider도 fallback과 테스트 용도로 남아 있습니다.

## 요구 사항

- Python 3.11+
- `bird` CLI 0.8.x 이상
- `codex` CLI 또는 Claude Code CLI 중 하나와 해당 CLI의 유효한 로그인
- 실제 전송 시 `TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHAT_ID`

## 설치

```powershell
cd D:\workspaces\tweet\x2telegram
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -e .
Copy-Item config.example.toml config.toml
Copy-Item .env.example .env
```

`.env`에는 실제 Telegram 값을 넣되 커밋하지 않습니다. `examples/accounts.txt`가 비어 있으면 following timeline의 모든 계정을 포함합니다. 특정 계정만 받으려면 한 줄에 하나씩 username을 적습니다.

## 안전한 첫 실행

먼저 dependency-free digest와 fixture로 전체 흐름을 확인합니다. 이 명령은 X, coding agent, Telegram에 접속하지 않고 상태 파일도 바꾸지 않습니다.

```powershell
x2telegram run --config config.digest.example.toml --input-json tests/fixtures/timeline.json --dry-run
```

그다음 fixture를 Codex 비대화형 모드로 요약해 adapter와 로그인을 확인합니다. X와 Telegram은 호출하지 않으며 상태도 바꾸지 않지만, Codex 사용량은 발생할 수 있습니다.

```powershell
x2telegram run --config config.example.toml --input-json tests/fixtures/timeline.json --dry-run
```

실제 X 타임라인을 읽되 Telegram으로 보내지 않으려면:

```powershell
x2telegram run --config config.toml --dry-run
```

설정과 로컬 도구만 점검하려면:

```powershell
x2telegram check --config config.toml
```

출력 내용을 확인한 뒤 실제 전송을 실행합니다.

```powershell
x2telegram run --config config.toml
```

실제 전송이 모두 성공한 뒤에만 `var/seen-tweets.json`이 갱신됩니다. 새 트윗이 없으면 메시지를 보내지 않습니다.

## 설정

```toml
[source]
provider = "bird"
timeline = "following" # following 또는 home
count = 100             # 항상 bounded read
accounts_file = "examples/accounts.txt"

[summary]
provider = "coding_agent"
agent = "codex"              # codex 또는 claude
executable = "codex"
prompt_file = "prompts/timeline-summary.md"
timeout_seconds = 180
max_input_items = 50          # coding-agent 입력 비용 상한
max_output_chars = 8000       # 비정상 출력 방지

[telegram]
env_file = ".env"
disable_web_page_preview = true

[state]
path = "var/seen-tweets.json"
```

모든 상대 경로는 `config.toml`의 위치를 기준으로 해석됩니다.

## Coding-agent 실행 경계

Codex adapter는 stdin으로 prompt와 트윗 JSON을 넘기고 다음 경계를 적용합니다.

- `codex exec --ephemeral --sandbox read-only`
- 비어 있는 임시 작업 디렉터리
- user config 미로딩, 세션 기록 미보존
- Telegram/X 관련 환경 변수 제거(Codex 자체 로그인 환경은 유지)
- 최종 응답 파일만 읽고 timeout/출력 크기 초과 시 실패

Claude Code adapter는 `config.claude.example.toml`을 사용합니다.

- `claude --print --output-format json --max-turns 1`
- `--safe-mode --tools "" --disallowedTools "mcp__*"`
- 세션 미보존, 빈 임시 작업 디렉터리

이 PC에는 현재 Claude Code CLI가 설치되어 있지 않아 Claude adapter는 mock 테스트로 검증됩니다. 설치 후 아래처럼 확인할 수 있습니다.

```powershell
Copy-Item config.claude.example.toml config.toml
x2telegram check --config config.toml
x2telegram run --config config.toml --input-json tests/fixtures/timeline.json --dry-run
```

Coding-agent 구독/로그인도 사용량 제한이나 별도 과금 정책이 적용될 수 있습니다. 비용 상한은 `source.count`, `max_input_items`, 실행 주기, 선택 모델로 관리합니다.

## 테스트

```powershell
$env:PYTHONPATH = "src"
python -m unittest discover -s tests -v
```

## 다음 확장 지점

- coding-agent 실패 시 명시적으로 선택 가능한 digest fallback
- X list/search source provider
- Windows Task Scheduler용 실행 스크립트
- 조사 queue와 상세 investigation 결과 전송
