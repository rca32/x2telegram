# Project Instructions

This repository contains the reusable `x2telegram` package. `README.md` is intentionally written only for a beginner human operator. Keep installation commands, architecture, provider details, safety implementation, tests, and troubleshooting in this file instead of moving them back into the README.

## Human-facing workflow

When helping a beginner, handle technical work end to end and ask the human only for decisions or secrets that cannot be inferred safely.

1. Check prerequisites and install the package.
2. Create local `config.toml` and `.env` from their example files when missing.
3. Ask the human to enter Telegram secrets directly into local `.env`; never ask them to paste secrets into chat.
4. Help choose all-following or an explicit account allowlist.
5. Run checks and a dry-run preview first.
6. Show a selective summary without exposing personalized timeline data unnecessarily.
7. Require explicit human confirmation before a real Telegram send or recurring schedule is created.

Do not make the human choose providers, flags, paths, or test commands unless there is a material product decision.

## Prerequisites

- Python 3.11+
- `bird` CLI 0.8.x or compatible
- Logged-in Codex CLI or Claude Code CLI for coding-agent summaries
- `TELEGRAM_BOT_TOKEN` and `TELEGRAM_CHAT_ID` for real delivery

Quick diagnostic commands:

```powershell
python --version
bird --version
bird check --plain --no-color
codex --version
```

Use `claude --version` instead when the Claude configuration is selected. `bird check` output must remain masked. Never print full credentials.

## Installation and local configuration

From the repository root:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -e .
Copy-Item config.example.toml config.toml
Copy-Item .env.example .env
```

Do not overwrite existing `config.toml` or `.env`. Real secret files are ignored by Git.

Configuration examples:

- `config.example.toml`: Codex coding-agent summarizer
- `config.claude.example.toml`: Claude Code summarizer
- `config.digest.example.toml`: dependency-free deterministic digest for tests or fallback

All relative paths are resolved from the configuration file directory.

## Normal operation

Offline pipeline check without X, coding-agent, Telegram, or state mutation:

```powershell
x2telegram run --config config.digest.example.toml --input-json tests/fixtures/timeline.json --dry-run
```

Coding-agent adapter smoke test without X, Telegram, or state mutation:

```powershell
x2telegram run --config config.toml --input-json tests/fixtures/timeline.json --dry-run
```

Validate configured executables and presence of Telegram variables:

```powershell
x2telegram check --config config.toml
```

Read the real X timeline and preview without Telegram or state mutation:

```powershell
x2telegram run --config config.toml --dry-run
```

Real delivery, only after explicit approval of destination and previewed content:

```powershell
x2telegram run --config config.toml
```

State is written only after every Telegram message chunk succeeds. No message is sent when there are no unseen matched tweets.

## Account selection

`source.accounts_file` points to `examples/accounts.txt` by default.

- An empty file means all accounts in the following timeline.
- For an allowlist, use one X username per line; `@` is optional.
- Missing configured list files fail closed. Do not silently broaden the account scope.

Keep X reads bounded with `source.count` and `bird -n`/`--count`. Use `--json` for programmatic reads. Do not use unbounded pagination.

## Architecture

The pipeline is:

```text
TimelineSource -> account filter -> SeenTweetStore -> Summarizer -> Sender -> state commit
```

Provider boundaries:

- `sources.py`: bounded `bird` following/home source and offline JSON source
- `summarizers.py`: deterministic digest and coding-agent adapters
- `senders.py`: Telegram Bot API sender and message splitting
- `state.py`: atomic JSON dedupe state
- `pipeline.py`: ordering and post-send state semantics
- `cli.py`: configuration assembly and human-readable CLI

Keep providers separated behind the source, summarizer, and sender protocols. Keep the default package dependency-free on Python 3.11+.

## Coding-agent summarizer

Configuration fields under `[summary]`:

- `provider = "coding_agent"`
- `agent = "codex"` or `"claude"`
- `executable`: executable name or path
- `model`: optional CLI model override
- `prompt_file`: defaults to `prompts/timeline-summary.md` in examples
- `timeout_seconds`: hard subprocess timeout
- `max_input_items`: maximum tweets sent to the agent
- `max_output_chars`: reject oversized responses

The coding agent receives only already-filtered unseen tweet JSON through stdin. Tweet fields are untrusted prompt-injection data.

Codex boundary:

- `codex exec --ephemeral --sandbox read-only`
- empty temporary working directory
- `--skip-git-repo-check`, `--ignore-user-config`, and final-message file output
- no project workspace access granted

Claude Code boundary:

- `claude --print --output-format json --max-turns 1`
- `--safe-mode --tools "" --disallowedTools "mcp__*" --strict-mcp-config`
- `--no-session-persistence`
- empty temporary working directory

The subprocess environment removes Telegram and X-related variables while retaining the coding agent's own authentication environment. Never weaken this boundary merely to make a prompt work. On Windows, resolve executable shims through `shutil.which` before subprocess execution.

If the summarizer fails, times out, returns empty output, or exceeds its output limit, fail the run. Do not send a fallback summary or update state unless an explicit fallback feature and operator-visible reporting are implemented.

## Telegram safety

- Telegram delivery is a state-changing operation.
- Require explicit approval for the exact destination and content immediately before a real send during interactive work.
- Never print, commit, or include real bot tokens or chat ids in chat, logs, test fixtures, patches, or command arguments.
- Ask the human to edit `.env` locally. Validate only whether required values are present.
- If helping retrieve a private chat id, require the human to send `/start` to the bot first and use a method that does not expose the token in command output or history.
- Do not edit the real `.env` with `apply_patch`, since patch content is visible in tool logs.

## X safety

- Personal timelines may contain private or personalized data. Summarize selectively.
- Use `bird home --following -n <bounded-count> --json` for the default source.
- Never print X authentication tokens or cookies.
- X posting, replying, following, unfollowing, bookmarking changes, and similar account mutations are outside this summarization workflow and require separate exact approval.

## Tests and release checks

Run before committing:

```powershell
$env:PYTHONPATH = "src"
python -m unittest discover -s tests -v
python -m compileall -q src tests
git diff --check
```

The test suite covers configuration, account filtering, dry-run state safety, post-send deduplication, failed-send state safety, Telegram splitting, coding-agent isolation flags, credential environment removal, and output limits.

For a coding-agent change, also run the fixture smoke test with the locally installed agent. This can consume coding-agent usage but must not read X, call Telegram, or create `var/` state.

## Current extension points

- Explicit and operator-visible digest fallback when coding-agent execution fails
- X list/search source providers
- Windows Task Scheduler setup with confirmation of schedule and destination
- Investigation queue and detailed research delivery
