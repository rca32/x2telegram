# Project Instructions

This repository contains the reusable `x2telegram` package. `README.md` is intentionally written only for a beginner human operator. Keep installation commands, architecture, provider details, safety implementation, tests, and troubleshooting in this file instead of moving them back into the README.

Before creating or changing Windows scheduled automation, read `docs/windows-task-scheduler-playbook.md` and preserve its trigger, hidden-launcher, preflight, locking, logging, and ACL invariants.

## Human-facing workflow

When helping a beginner, handle technical work end to end and ask the human only for decisions or secrets that cannot be inferred safely.

1. Check prerequisites and install the package.
2. Create local `config.toml` and Telegram `.env` from their example files when missing.
3. Prefer browser-cookie extraction for X. Create `x-oauth.env` from its example only when manual fallback is necessary.
4. Ask the human to enter X and Telegram secrets directly into their respective local env files; never ask them to paste secrets into chat.
5. Help choose all-following or an explicit account allowlist.
6. Run checks and a dry-run preview first.
7. Treat blank/sample Telegram values as not configured and perform a read-only destination probe before claiming delivery readiness.
8. Show a selective summary without exposing personalized timeline data unnecessarily.
9. Require explicit human confirmation before a real Telegram send or recurring schedule is created.

Do not make the human choose providers, flags, paths, or test commands unless there is a material product decision.

## Prerequisites

- Python 3.11+
- `bird` CLI 0.8.x or compatible
- Logged-in Codex CLI or Claude Code CLI for coding-agent summaries
- `TELEGRAM_BOT_TOKEN` and `TELEGRAM_CHAT_ID` for real delivery
- Node.js 22+ when installing the npm-distributed bird CLI on Linux/WSL

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

For the manual X-cookie fallback only:

```powershell
Copy-Item x-oauth.env.example x-oauth.env
```

Do not overwrite existing `config.toml`, `.env`, or `x-oauth.env`. Local config and secret files are ignored by Git.

The tracked env example files intentionally contain blank values. Never put convincing fake secrets such as `replace-me` in examples because presence-only scripts and humans can mistake them for completed setup.

To verify local ignores in PowerShell, prefer `git check-ignore -v -- config.toml .env`. `git check-ignore -q` accepts only one pathname and intentionally writes no stdout; run it once per path and inspect `$LASTEXITCODE` immediately instead of casting its empty output to `[bool]`.

Configuration examples:

- `config.example.toml`: Codex coding-agent summarizer
- `config.claude.example.toml`: Claude Code summarizer
- `config.digest.example.toml`: dependency-free deterministic digest for tests or fallback

All relative paths are resolved from the configuration file directory.

## Linux and WSL onboarding

Use Linux-native executables inside WSL. A `command -v bird` or `command -v codex` result under `/mnt/c/.../AppData/.../npm` is a Windows npm shim leaking through the WSL PATH, not a valid Linux installation for this workflow. `x2telegram check` and timeline runs must fail with an actionable error when bird resolves this way.

The npm-distributed bird 0.8.0 requires Node.js 22 or newer. Prefer an existing user-local version manager and do not use `sudo` merely to make onboarding pass:

```bash
source "$HOME/.nvm/nvm.sh"
nvm install 22
nvm use 22
npm view @steipete/bird@0.8.0 engines deprecated
npm install -g @steipete/bird@0.8.0
npm install -g @openai/codex
hash -r
node --version
command -v bird
bird --version
command -v codex
codex --version
```

As observed on 2026-07-13, npm marks `@steipete/bird@0.8.0` deprecated even though it is the currently tested provider. Keep the tested version pinned, report the warning, and track a replacement separately; do not silently switch packages or weaken tests during onboarding.

Install the Python package with Linux paths and protect local secret files:

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -e .
cp config.example.toml config.toml
cp .env.example .env
cp x-oauth.env.example x-oauth.env
chmod 600 .env x-oauth.env
```

Windows browser-cookie extraction generally does not transfer into WSL. A copied file named `x-oauth.env` may contain developer OAuth client credentials rather than browser session cookies. The only keys accepted by this project's manual bird fallback are `AUTH_TOKEN` and `CT0`; validate key presence without printing values. Developer API/OAuth keys are not substitutes.

For a one-off Windows-launched WSL process, existing Windows session-cookie environment variables can be bridged without creating another file. On this host, empirical WSL2 behavior uses the `/u` flag for Win32-to-WSL propagation:

```powershell
$previousWslenv = $env:WSLENV
$parts = @($previousWslenv, "AUTH_TOKEN/u", "CT0/u") | Where-Object { $_ }
$env:WSLENV = $parts -join ":"
wsl.exe -d Ubuntu -- bash -lc 'cd /path/to/x2telegram && x2telegram check --config config.toml'
$env:WSLENV = $previousWslenv
```

Verify direction with a non-secret probe if host behavior is uncertain. Never echo the real variables. For unattended Linux scheduling, prefer WSL-local owner-only env files (`chmod 600`) over a transient Windows environment bridge.

The configured Codex CLI must support `--ephemeral`, `--sandbox`, `--skip-git-repo-check`, `--ignore-user-config`, and `--output-last-message`. `x2telegram check` probes these options and must reject an older incompatible CLI instead of silently dropping a security boundary.

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

This returns success when preview prerequisites are ready even if Telegram is not configured. Blank values and placeholders such as `replace-me`, `your-*`, and `여기에_*` are not credentials. Require delivery readiness explicitly when needed:

```powershell
x2telegram check --config config.toml --require-telegram
```

When non-placeholder Telegram values exist, the check performs read-only Bot API `getMe` and `getChat` calls. It prints a bounded bot/destination display label without the token or raw chat id and sends no message. Do not claim delivery readiness merely because both environment variables are non-empty. A successful destination probe still does not replace the human's approval of the exact first message.

Read the real X timeline and preview without Telegram or state mutation:

```powershell
x2telegram run --config config.toml --count 10 --dry-run
```

Real delivery, only after explicit approval of destination and previewed content:

```powershell
x2telegram run --config config.toml
```

State is written only after every Telegram message chunk succeeds. No message is sent when there are no unseen matched tweets.

## Account selection

`source.accounts_file` is empty by default, which includes all accounts in the bounded following timeline.

- For an allowlist, copy `examples/accounts.txt` to the ignored local `accounts.txt`, add one X username per line (`@` is optional), and set `accounts_file = "accounts.txt"` in ignored local `config.toml`.
- Missing configured list files fail closed. Do not silently broaden the account scope.
- Never place a personal account allowlist in tracked example files.

Keep X reads bounded with `source.count` and `bird -n`/`--count`. The example default is 20; use `x2telegram run --count <n>` for a smaller one-off preview. Use `--json` for programmatic reads. Do not use unbounded pagination.

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

`x2telegram check` validates the required Codex non-interactive options. Do not bypass a compatibility failure by removing isolation flags; install a compatible Linux-native Codex CLI instead.

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
- Ask the human to edit `.env` locally. Reject blank and sample values, then use only read-only `getMe`/`getChat` probes to validate the bot and destination before a send is approved.
- Report a bounded destination title or username, never the raw chat id. Say `configured but not reachable` when the API probe fails; do not collapse it into `ready`.
- A destination probe is not a send-permission proof and must never trigger a test message implicitly.
- If helping retrieve a private chat id, require the human to send `/start` to the bot first and use a method that does not expose the token in command output or history.
- Do not edit the real `.env` with `apply_patch`, since patch content is visible in tool logs.

## X safety

- Personal timelines may contain private or personalized data. Summarize selectively.
- Use `bird home --following -n <bounded-count> --json` for the default source.
- Never print X authentication tokens or cookies.
- X posting, replying, following, unfollowing, bookmarking changes, and similar account mutations are outside this summarization workflow and require separate exact approval.

### X authentication setup

The required X session cookies are `auth_token` and `ct0`. Prefer browser extraction so the human does not have to handle their values.

Safe masked checks:

```powershell
bird check --plain --no-color
bird whoami --plain --no-color
```

Report only readiness, credential source, and the intended account. `bird check` masks values; preserve that masking. `whoami` may expose personalized account identity, so summarize selectively.

Prefer `x2telegram check --config config.toml` during onboarding. Upstream `bird check` may say `Ready to tweet!` even when it is used only to verify read credentials; this is generic upstream wording and does not mean x2telegram posted or will post anything.

If the default browser profile is not detected, try an explicit profile without exposing cookies:

```powershell
bird --chrome-profile Default check --plain --no-color
bird --chrome-profile "Profile 1" check --plain --no-color
bird --firefox-profile default-release check --plain --no-color
```

`bird` also supports `--chrome-profile-dir`, repeatable `--cookie-source`, and the non-secret profile fields in `~/.config/bird/config.json5` or local `.birdrc.json5`. Inspect `bird --help` before using version-sensitive options. Prefer a browser-profile setting over copying cookies manually.

Manual fallback:

1. Ask the human to sign in to `x.com` and find `auth_token` and `ct0` under the browser developer tools' X cookies.
2. Create `x-oauth.env` from `x-oauth.env.example` without real values.
3. Ask the human to edit the local file directly.
4. The file must contain `AUTH_TOKEN=<auth_token cookie>` and `CT0=<ct0 cookie>`.
5. Run `x2telegram check --config config.toml`; it loads `source.auth_env_file`, calls the masked `bird check`, and prints only readiness.
6. Verify `x-oauth.env` remains ignored with `git check-ignore -v x-oauth.env`.

Never pass real values through `bird --auth-token` or `bird --ct0` during assisted work because command arguments can appear in tool logs, command history, and process listings. Do not read or print an existing `x-oauth.env`. The coding-agent summarizer subprocess must continue stripping `AUTH_TOKEN`, `CT0`, and related X variables.

## Windows scheduled automation

Use the repository-managed scripts. Do not assemble `schtasks /TR` strings or rewrite a live task action for diagnostics.

- `scripts/install-windows-scheduled-task.ps1`: protect secrets, run strict/read-only preflights, and idempotently register the task
- `scripts/run-windows-scheduled-task-hidden.vbs`: launch the PowerShell runner through console-free `wscript.exe` and wait for its exit code
- `scripts/run-windows-scheduled-task.ps1`: invoke a quiet bounded run and append only sanitized JSONL status/count records
- `scripts/get-windows-scheduled-task-status.ps1`: report trigger/settings/result and the latest safe log record
- `scripts/protect-local-secrets.ps1`: idempotently remove inherited/extra ACLs and grant access only to the current user, SYSTEM, and Administrators
- `scripts/remove-windows-scheduled-task.ps1`: explicitly unregister the task

Install the confirmed 08:00-22:00 daily schedule with a 30-minute interval and the same 10-item scope used in preview:

```powershell
.\scripts\install-windows-scheduled-task.ps1 `
  -ProjectRoot (Get-Location).Path `
  -StartTime "08:00" `
  -EndTime "22:00" `
  -IntervalMinutes 30 `
  -Count 10 `
  -Enable
```

The installer must preserve these invariants:

- a `CalendarTrigger` with `DaysInterval=1`; no dated `EndBoundary`
- a repetition window that includes the end-time run but stops afterward each day
- explicit `-Count 10` in the managed runner action
- `wscript.exe //B //NoLogo` as the registered action so an interactive task never opens or flashes a console window
- strict Telegram destination check and matching bounded dry-run before task replacement
- existing seen-state by default; use `-AllowInitialBacklog` only after explicit approval to send an unreviewed initial backlog
- `StartWhenAvailable`, network requirement, wake support, battery allowance, 15-minute execution limit, two 5-minute retries, and `IgnoreNew`
- `InteractiveToken`/least privilege, because Codex authentication and network access belong to the logged-in user

The task therefore does not run while the user is fully logged out. Explain this limitation instead of silently switching to SYSTEM or embedding a Windows password.

Every CLI run acquires an OS-level lock next to the seen-state. A concurrent scheduled or manual run must fail safely as `already_running`. Never remove the lock or allow overlapping state writers to make a test pass.

The scheduled action must remain the managed VBS launcher, which uses `WScript.Shell.Run` with window style `0` and waits for the PowerShell runner's exit code. The runner also uses `-WindowStyle Hidden` as defense in depth and `--quiet`; it must never persist digest text, tweet URLs, credentials, or raw exception output. Its daily JSONL logs under `var/logs/` contain only timestamp, status category, exit code, bounded count, and the final numeric run summary. Diagnose with these logs and `LastTaskResult`; do not temporarily replace the registered action.

Before enabling a new automation, complete one human-approved manual send so seen-state exists. Registering and preflighting an automation must not itself send a Telegram message.

## Tests and release checks

Run before committing:

```powershell
$env:PYTHONPATH = "src"
python -m unittest discover -s tests -v
python -m compileall -q src tests
git diff --check
```

The test suite covers configuration, account filtering, dry-run state safety, post-send deduplication, failed-send state safety, Telegram splitting, placeholder rejection, read-only destination probing, coding-agent isolation flags, credential environment removal, Windows command-shim resolution, preview-vs-delivery readiness, and output limits.

For a coding-agent change, also run the fixture smoke test with the locally installed agent. This can consume coding-agent usage but must not read X, call Telegram, or create `var/` state.

## Current extension points

- Explicit and operator-visible digest fallback when coding-agent execution fails
- X list/search source providers
- Investigation queue and detailed research delivery
