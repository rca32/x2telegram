# x2telegram

`x2telegram`은 X 타임라인을 제한된 범위로 읽고, 새 트윗만 digest로 요약해 Telegram으로 보내는 재사용 가능한 Python 패키지입니다.

현재 기본 구성은 다음과 같습니다.

- Source: 로컬 `bird` CLI의 home/following timeline
- Summarizer: 키워드와 반응 수로 중요도를 정하는 dependency-free digest
- Sender: Telegram Bot API `sendMessage`
- State: 성공적으로 전송한 tweet id를 JSON에 저장하는 dedupe store

source, summarizer, sender는 각각 인터페이스로 분리되어 있어 이후 검색 결과, list timeline, LLM 요약기, 다른 메신저를 독립적으로 추가할 수 있습니다.

## 요구 사항

- Python 3.11+
- `bird` CLI 0.8.x 이상
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

먼저 fixture로 전체 흐름을 확인합니다. 이 명령은 X와 Telegram에 접속하지 않고 상태 파일도 바꾸지 않습니다.

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
provider = "digest"
title = "X timeline digest"
max_items = 12
max_chars_per_item = 280
keywords_file = "examples/keywords.txt"

[telegram]
env_file = ".env"
disable_web_page_preview = true

[state]
path = "var/seen-tweets.json"
```

모든 상대 경로는 `config.toml`의 위치를 기준으로 해석됩니다.

## 테스트

```powershell
$env:PYTHONPATH = "src"
python -m unittest discover -s tests -v
```

## 다음 확장 지점

- LLM summarizer provider와 프롬프트/토큰 예산 설정
- X list/search source provider
- Windows Task Scheduler용 실행 스크립트
- 조사 queue와 상세 investigation 결과 전송
