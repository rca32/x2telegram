from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
from pathlib import Path

from .config import AppConfig, load_config, load_env, read_list
from .pipeline import Pipeline
from .senders import TelegramSender
from .sources import BirdTimelineSource, JsonFileTimelineSource, TimelineSource
from .state import SeenTweetStore
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
    run.add_argument("--dry-run", action="store_true", help="print only; do not send or update state")

    check = subparsers.add_parser("check", help="validate local commands and configuration")
    check.add_argument("--config", default="config.toml", help="TOML configuration path")
    return parser


def _source(config: AppConfig, input_json: str | None) -> TimelineSource:
    if input_json:
        return JsonFileTimelineSource(Path(input_json).expanduser().resolve())
    return BirdTimelineSource(
        count=config.source.count,
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


def _pipeline(config: AppConfig, *, input_json: str | None, dry_run: bool) -> Pipeline:
    accounts = read_list(config.source.accounts_file)
    sender = None
    if not dry_run:
        load_env(config.telegram.env_file)
        sender = TelegramSender(disable_web_page_preview=config.telegram.disable_web_page_preview)
    return Pipeline(
        source=_source(config, input_json),
        summarizer=_summarizer(config),
        sender=sender,
        state=SeenTweetStore(config.state.path),
        accounts=accounts,
    )


def _run(args: argparse.Namespace) -> int:
    config = load_config(args.config)
    result = _pipeline(config, input_json=args.input_json, dry_run=args.dry_run).run(dry_run=args.dry_run)
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


def _check(args: argparse.Namespace) -> int:
    config = load_config(args.config)
    executable = shutil.which(config.source.executable)
    if executable is None:
        raise RuntimeError(f"bird CLI was not found: {config.source.executable}")
    result = subprocess.run(
        [executable, "--version"], capture_output=True, text=True, encoding="utf-8", errors="replace"
    )
    if result.returncode != 0:
        raise RuntimeError("bird --version failed")
    agent_status = "not configured"
    if config.summary.provider == "coding_agent":
        agent_executable = config.summary.executable or config.summary.agent
        resolved_agent = shutil.which(agent_executable)
        if resolved_agent is None:
            raise RuntimeError(f"coding agent CLI was not found: {agent_executable}")
        agent_status = f"{config.summary.agent} available"
    load_env(config.telegram.env_file)
    telegram_ready = bool(os.environ.get("TELEGRAM_BOT_TOKEN") and os.environ.get("TELEGRAM_CHAT_ID"))
    print(f"Configuration: {Path(args.config).resolve()}")
    print(f"bird: {result.stdout.strip() or 'available'}")
    print(f"Coding agent: {agent_status}")
    print(f"Telegram credentials: {'present' if telegram_ready else 'missing'}")
    print("No timeline was read and no Telegram message was sent.")
    return 0 if telegram_ready else 2


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
