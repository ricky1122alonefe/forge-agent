"""LLMConfig — declarative, user-owned configuration.

**File layout (project-local, never auto-uploaded):**

    my_app/
    ├── llm_providers.json          # non-secret config (CAN be in git if user wants)
    └── .env                        # secret keys (NEVER in git)

**Default search order:**

    1. $FORGE_LLM_CONFIG env var (explicit path)
    2. ./llm_providers.json
    3. ./llm_providers.example.json
    4. forge-agent built-in defaults (deepseek + ollama)
"""

from __future__ import annotations

import json
import logging
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

log = logging.getLogger(__name__)

ENV_CONFIG_PATH = "FORGE_LLM_CONFIG"

BUILTIN_DEFAULTS: dict[str, Any] = {
    "version": 1,
    "primary_id": "deepseek",
    "predict_mode": "single",  # "single" | "multi" | "fallback"
    "providers": {
        "deepseek": {
            "type": "deepseek",
            "model": "deepseek-chat",
            "base_url": "https://api.deepseek.com/v1",
            "api_key_env": "DEEPSEEK_API_KEY",
            "enabled": True,
            "weight": 1.0,
            "tags": ["chat", "code", "chinese"],
        },
        "ollama": {
            "type": "ollama",
            "model": "qwen2.5:7b",
            "base_url": "http://localhost:11434/v1",
            "api_key_env": "OLLAMA_API_KEY",  # optional, ollama usually doesn't need
            "enabled": False,
            "weight": 0.5,
            "tags": ["local", "free"],
        },
    },
    "multi": {"on_disagreement": "vote", "min_agreement": 0.5},
}


@dataclass
class ProviderConfig:
    """One LLM provider's settings."""

    provider_id: str
    type: str
    model: str
    base_url: str | None = None
    api_key_env: str | None = None
    alt_envs: list[str] = field(default_factory=list)
    enabled: bool = True
    weight: float = 1.0
    tags: list[str] = field(default_factory=list)
    extra: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_dict(cls, pid: str, data: dict[str, Any]) -> "ProviderConfig":
        return cls(
            provider_id=pid,
            type=str(data.get("type", pid)),
            model=str(data.get("model", "")),
            base_url=data.get("base_url"),
            api_key_env=data.get("api_key_env"),
            alt_envs=list(data.get("alt_envs", [])),
            enabled=bool(data.get("enabled", True)),
            weight=float(data.get("weight", 1.0)),
            tags=list(data.get("tags", [])),
            extra={k: v for k, v in data.items() if k not in {
                "type", "model", "base_url", "api_key_env", "alt_envs",
                "enabled", "weight", "tags",
            }},
        )


@dataclass
class LLMConfig:
    """Top-level LLM configuration."""

    primary_id: str
    predict_mode: str
    providers: dict[str, ProviderConfig]
    multi: dict[str, Any] = field(default_factory=dict)
    source_path: Path | None = None

    def get_enabled(self) -> list[ProviderConfig]:
        return [p for p in self.providers.values() if p.enabled]

    def get(self, provider_id: str) -> ProviderConfig | None:
        return self.providers.get(provider_id)

    def primary(self) -> ProviderConfig:
        p = self.providers.get(self.primary_id)
        if p is None:
            from forge_agent.exceptions import ProviderNotConfiguredError
            raise ProviderNotConfiguredError(self.primary_id, available=list(self.providers.keys()))
        return p


def load_config(
    *,
    explicit_path: str | Path | None = None,
    search_paths: list[str | Path] | None = None,
) -> LLMConfig:
    """Load config from file or fall back to built-in defaults.

    Resolution:
        1. explicit_path argument
        2. $FORGE_LLM_CONFIG env var
        3. ./llm_providers.json
        4. ./llm_providers.example.json
        5. built-in defaults (deepseek + ollama, deepseek disabled if no key)
    """
    candidates: list[Path] = []
    if explicit_path:
        candidates.append(Path(explicit_path))
    env_path = os.environ.get(ENV_CONFIG_PATH)
    if env_path:
        candidates.append(Path(env_path))
    for s in (search_paths or [Path.cwd()]):
        candidates.append(Path(s) / "llm_providers.json")
    for s in (search_paths or [Path.cwd()]):
        candidates.append(Path(s) / "llm_providers.example.json")

    data: dict[str, Any] = {}
    source: Path | None = None
    for c in candidates:
        if c.is_file():
            try:
                data = json.loads(c.read_text(encoding="utf-8"))
                source = c
                log.info("LLM config loaded from %s", c)
                break
            except json.JSONDecodeError:
                log.warning("LLM config at %s is invalid JSON, skipping", c)

    if not data:
        log.info("No llm_providers.json found; using built-in defaults")
        data = json.loads(json.dumps(BUILTIN_DEFAULTS))  # deep copy
        source = None

    return _parse_config(data, source=source)


def _parse_config(data: dict[str, Any], *, source: Path | None) -> LLMConfig:
    providers: dict[str, ProviderConfig] = {}
    for pid, pdata in (data.get("providers") or {}).items():
        if not isinstance(pdata, dict):
            continue
        providers[pid] = ProviderConfig.from_dict(pid, pdata)
    return LLMConfig(
        primary_id=str(data.get("primary_id", "deepseek")),
        predict_mode=str(data.get("predict_mode", "single")),
        providers=providers,
        multi=dict(data.get("multi") or {}),
        source_path=source,
)
