from __future__ import annotations

import os
import tomllib
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True, slots=True)
class SourceConfig:
    provider: str = "bird"
    timeline: str = "following"
    count: int = 20
    executable: str = "bird"
    accounts_file: Path | None = None
    auth_env_file: Path | None = None


@dataclass(frozen=True, slots=True)
class SummaryConfig:
    provider: str = "digest"
    title: str = "X timeline digest"
    max_items: int = 12
    max_chars_per_item: int = 280
    keywords_file: Path | None = None
    agent: str = "codex"
    executable: str = ""
    model: str = ""
    prompt_file: Path | None = None
    timeout_seconds: int = 180
    max_input_items: int = 50
    max_output_chars: int = 8000


@dataclass(frozen=True, slots=True)
class TelegramConfig:
    env_file: Path | None = None
    disable_web_page_preview: bool = True


@dataclass(frozen=True, slots=True)
class StateConfig:
    path: Path = Path("var/seen-tweets.json")


@dataclass(frozen=True, slots=True)
class AppConfig:
    source: SourceConfig
    summary: SummaryConfig
    telegram: TelegramConfig
    state: StateConfig


def _path(base: Path, value: object) -> Path | None:
    if value is None or str(value).strip() == "":
        return None
    candidate = Path(str(value)).expanduser()
    return candidate if candidate.is_absolute() else (base / candidate).resolve()


def load_config(path: str | Path) -> AppConfig:
    config_path = Path(path).expanduser().resolve()
    with config_path.open("rb") as stream:
        data = tomllib.load(stream)

    base = config_path.parent
    source = data.get("source", {})
    summary = data.get("summary", {})
    telegram = data.get("telegram", {})
    state = data.get("state", {})

    source_config = SourceConfig(
        provider=str(source.get("provider", "bird")),
        timeline=str(source.get("timeline", "following")),
        count=int(source.get("count", 20)),
        executable=str(source.get("executable", "bird")),
        accounts_file=_path(base, source.get("accounts_file")),
        auth_env_file=_path(base, source.get("auth_env_file")),
    )
    summary_config = SummaryConfig(
        provider=str(summary.get("provider", "digest")),
        title=str(summary.get("title", "X timeline digest")),
        max_items=int(summary.get("max_items", 12)),
        max_chars_per_item=int(summary.get("max_chars_per_item", 280)),
        keywords_file=_path(base, summary.get("keywords_file")),
        agent=str(summary.get("agent", "codex")),
        executable=str(summary.get("executable", "")),
        model=str(summary.get("model", "")),
        prompt_file=_path(base, summary.get("prompt_file")),
        timeout_seconds=int(summary.get("timeout_seconds", 180)),
        max_input_items=int(summary.get("max_input_items", 50)),
        max_output_chars=int(summary.get("max_output_chars", 8000)),
    )
    state_path = _path(base, state.get("path", "var/seen-tweets.json"))
    config = AppConfig(
        source=source_config,
        summary=summary_config,
        telegram=TelegramConfig(
            env_file=_path(base, telegram.get("env_file", ".env")),
            disable_web_page_preview=bool(telegram.get("disable_web_page_preview", True)),
        ),
        state=StateConfig(path=state_path or (base / "var/seen-tweets.json")),
    )
    _validate(config)
    return config


def _validate(config: AppConfig) -> None:
    if config.source.provider != "bird":
        raise ValueError(f"unsupported source provider: {config.source.provider}")
    if config.source.timeline not in {"home", "following"}:
        raise ValueError("source.timeline must be 'home' or 'following'")
    if not 1 <= config.source.count <= 1000:
        raise ValueError("source.count must be between 1 and 1000")
    if config.summary.provider not in {"digest", "coding_agent"}:
        raise ValueError(f"unsupported summary provider: {config.summary.provider}")
    if config.summary.max_items < 1:
        raise ValueError("summary.max_items must be at least 1")
    if config.summary.max_chars_per_item < 40:
        raise ValueError("summary.max_chars_per_item must be at least 40")
    if config.summary.agent not in {"codex", "claude"}:
        raise ValueError("summary.agent must be 'codex' or 'claude'")
    if config.summary.timeout_seconds < 1:
        raise ValueError("summary.timeout_seconds must be at least 1")
    if config.summary.max_input_items < 1:
        raise ValueError("summary.max_input_items must be at least 1")
    if config.summary.max_output_chars < 100:
        raise ValueError("summary.max_output_chars must be at least 100")
    if config.summary.provider == "coding_agent" and config.summary.prompt_file is None:
        raise ValueError("summary.prompt_file is required for the coding_agent provider")


def read_list(path: Path | None) -> list[str]:
    if path is None:
        return []
    if not path.exists():
        raise FileNotFoundError(f"configured list file was not found: {path}")
    return [
        line
        for raw in path.read_text(encoding="utf-8-sig").splitlines()
        if (line := raw.strip()) and not line.startswith("#")
    ]


def load_env(path: Path | None) -> None:
    if path is None or not path.exists():
        return
    for raw in path.read_text(encoding="utf-8-sig").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in {'"', "'"}:
            value = value[1:-1]
        if key:
            os.environ.setdefault(key, value)
