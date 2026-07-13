from __future__ import annotations

import argparse
import os
import subprocess
import sys
from pathlib import Path

from .config import AppConfig, load_config, load_env, read_env_keys, read_list
from .pipeline import Pipeline
from .senders import (
    TelegramSender,
    probe_telegram_destination,
    telegram_credentials_are_configured,
)
from .sources import (
    BirdTimelineSource,
    JsonFileTimelineSource,
    TimelineSource,
    find_executable,
    is_wsl_windows_npm_shim,
)
from .state import RunLock, SeenTweetStore
from .summarizers import CodingAgentSummarizer, DigestSummarizer, Summarizer


def _configure_stdio() -> None:
    for stream in (sys.stdout, sys.stderr):
        reconfigure = getattr(stream, "reconfigure", None)
        if reconfigure is not None:
            reconfigure(encoding="utf-8", errors="replace")


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="x2telegram", description="Build and send a digest from a bounded X timeline."
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    run = subparsers.add_parser("run", help="read, summarize, and optionally send the timeline")
    run.add_argument("--config", default="config.toml", help="TOML configuration path")
    run.add_argument("--input-json", help="offline bird JSON fixture instead of invoking bird")
    run.add_argument("--count", type=int, help="override the bounded timeline read count")
    run.add_argument("--dry-run", action="store_true", help="print only; do not send or update state")
    run.add_argument("--quiet", action="store_true", help="suppress digest text; keep safe counts")

    check = subparsers.add_parser("check", help="validate local commands and configuration")
    check.add_argument("--config", default="config.toml", help="TOML configuration path")
    check.add_argument(
        "--require-telegram",
        action="store_true",
        help="return exit code 2 when Telegram delivery credentials are missing",
    )
    return parser


def _source(
    config: AppConfig, input_json: str | None, count_override: int | None = None
) -> TimelineSource:
    if input_json:
        return JsonFileTimelineSource(Path(input_json).expanduser().resolve())
    count = count_override if count_override is not None else config.source.count
    if not 1 <= count <= 1000:
        raise ValueError("--count must be between 1 and 1000")
    return BirdTimelineSource(
        count=count,
        timeline=config.source.timeline,
        executable=config.source.executable,
    )


def _summarizer(config: AppConfig) -> Summarizer:
    if config.summary.provider == "coding_agent":
        prompt_path = config.summary.prompt_file
        if prompt_path is None or not prompt_path.exists():
            raise FileNotFoundError(f"summary prompt file was not found: {prompt_path}")
        return CodingAgentSummarizer(
            agent=config.summary.agent,
            executable=config.summary.executable,
            model=config.summary.model,
            reasoning_effort=config.summary.reasoning_effort,
            prompt=prompt_path.read_text(encoding="utf-8-sig"),
            timeout_seconds=config.summary.timeout_seconds,
            max_input_items=config.summary.max_input_items,
            max_output_chars=config.summary.max_output_chars,
        )
    return DigestSummarizer(
        title=config.summary.title,
        max_items=config.summary.max_items,
        max_chars_per_item=config.summary.max_chars_per_item,
        keywords=read_list(config.summary.keywords_file),
    )


def _pipeline(
    config: AppConfig, *, input_json: str | None, dry_run: bool, count_override: int | None = None
) -> Pipeline:
    load_env(config.source.auth_env_file)
    accounts = read_list(config.source.accounts_file)
    sender = None
    if not dry_run:
        load_env(config.telegram.env_file)
        sender = TelegramSender(disable_web_page_preview=config.telegram.disable_web_page_preview)
    return Pipeline(
        source=_source(config, input_json, count_override),
        summarizer=_summarizer(config),
        sender=sender,
        state=SeenTweetStore(config.state.path),
        accounts=accounts,
    )


def _run(args: argparse.Namespace) -> int:
    config = load_config(args.config)
    lock_path = config.state.path.with_name(f"{config.state.path.name}.lock")
    with RunLock(lock_path):
        result = _pipeline(
            config, input_json=args.input_json, dry_run=args.dry_run, count_override=args.count
        ).run(dry_run=args.dry_run)
    if not args.quiet:
        if result.digest:
            print(result.digest)
        else:
            print("No new tweets.")
    print(
        f"\nFetched: {result.fetched_count}; matched: {result.matched_count}; "
        f"new: {result.new_count}; sent chunks: {result.sent_chunks}"
    )
    if args.dry_run:
        print("Dry run: Telegram was not called and state was not changed.")
    return 0


def _check_coding_agent(config: AppConfig) -> str:
    if config.summary.provider != "coding_agent":
        return "not configured"

    agent = config.summary.agent
    agent_executable = config.summary.executable or agent
    resolved = find_executable(agent_executable)
    if resolved is None:
        raise RuntimeError(f"coding agent CLI was not found: {agent_executable}")

    if agent == "codex":
        result = subprocess.run(
            [resolved, "exec", "--help"],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
        )
        if result.returncode != 0:
            raise RuntimeError("codex exec --help failed")
        help_text = f"{result.stdout}\n{result.stderr}"
        required = (
            "--config",
            "--strict-config",
            "--ephemeral",
            "--sandbox",
            "--skip-git-repo-check",
            "--ignore-user-config",
            "--output-last-message",
        )
        missing = [option for option in required if option not in help_text]
        if missing:
            raise RuntimeError(
                "codex CLI is too old or incompatible; missing required options: "
                + ", ".join(missing)
            )
        model = config.summary.model or "CLI default"
        reasoning = config.summary.reasoning_effort or "CLI default"
        return f"codex available and compatible; model: {model}; reasoning: {reasoning}"

    result = subprocess.run(
        [resolved, "--version"],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    if result.returncode != 0:
        raise RuntimeError("claude --version failed")
    return "claude available"


def _check(args: argparse.Namespace) -> int:
    config = load_config(args.config)
    auth_env_keys = read_env_keys(config.source.auth_env_file)
    load_env(config.source.auth_env_file)
    executable = find_executable(config.source.executable)
    if executable is None:
        raise RuntimeError(f"bird CLI was not found: {config.source.executable}")
    if is_wsl_windows_npm_shim(executable):
        raise RuntimeError(
            "bird resolves to a Windows npm shim inside WSL; activate Linux-native Node 22+ "
            "and install a Linux-native bird CLI earlier in PATH"
        )
    result = subprocess.run(
        [executable, "--version"], capture_output=True, text=True, encoding="utf-8", errors="replace"
    )
    if result.returncode != 0:
        raise RuntimeError("bird --version failed")
    credential_result = subprocess.run(
        [executable, "check", "--plain", "--no-color"],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    if credential_result.returncode != 0:
        required_cookie_keys = {"AUTH_TOKEN", "CT0"}
        if config.source.auth_env_file is not None and config.source.auth_env_file.exists():
            if not required_cookie_keys.issubset(auth_env_keys):
                raise RuntimeError(
                    "the configured X auth env file does not contain AUTH_TOKEN and CT0; "
                    "developer OAuth client credentials are not browser session cookies"
                )
        raise RuntimeError(
            "X credentials are not ready; sign in to X in a supported browser or configure x-oauth.env"
        )
    agent_status = _check_coding_agent(config)
    load_env(config.telegram.env_file)
    bot_token = os.environ.get("TELEGRAM_BOT_TOKEN", "")
    chat_id = os.environ.get("TELEGRAM_CHAT_ID", "")
    telegram_ready = False
    if telegram_credentials_are_configured(bot_token, chat_id):
        try:
            telegram_destination = probe_telegram_destination(bot_token, chat_id)
        except (RuntimeError, ValueError) as exc:
            telegram_status = f"configured but not reachable ({exc})"
        else:
            telegram_ready = True
            telegram_status = f"ready: {telegram_destination}"
    else:
        telegram_status = "not configured (replace the sample values in .env)"
    print(f"Configuration: {Path(args.config).resolve()}")
    print(f"bird: {result.stdout.strip() or 'available'}")
    print("X credentials: ready (values hidden)")
    print(f"Coding agent: {agent_status}")
    print("Preview readiness: ready")
    print(f"Telegram delivery: {telegram_status}")
    print("No timeline was read and no Telegram message was sent.")
    return 2 if args.require_telegram and not telegram_ready else 0


def main(argv: list[str] | None = None) -> int:
    _configure_stdio()
    args = _parser().parse_args(argv)
    try:
        if args.command == "run":
            return _run(args)
        if args.command == "check":
            return _check(args)
        raise RuntimeError(f"unknown command: {args.command}")
    except (OSError, RuntimeError, ValueError) as exc:
        print(f"x2telegram: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
