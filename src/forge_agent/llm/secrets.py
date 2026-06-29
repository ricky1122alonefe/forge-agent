"""APIKeyManager — multi-source API key resolution.

**Lookup priority (high to low):**

    1. explicit argument
    2. process environment variable
    3. .env file (loaded via python-dotenv if available, else parsed manually)
    4. local_secrets.py (mirrors guess_you_like convention)
    5. system keyring (optional, best-effort)

**forge-agent NEVER persists keys.** It only reads them.
"""

from __future__ import annotations

import logging
import os
from collections.abc import Iterable
from dataclasses import dataclass
from enum import Enum
from pathlib import Path

log = logging.getLogger(__name__)


class APIKeySource(str, Enum):
    EXPLICIT = "explicit"
    ENV = "env"
    DOTENV = "dotenv"
    LOCAL_SECRETS = "local_secrets"
    KEYRING = "keyring"
    MISSING = "missing"


@dataclass
class ResolvedKey:
    value: str
    source: APIKeySource
    name: str


class APIKeyManager:
    """Resolve API keys from multiple sources.

    Usage::

        km = APIKeyManager()
        key = km.resolve("DEEPSEEK_API_KEY", search_paths=["./"])
        if not key:
            raise LLMAuthError("DEEPSEEK_API_KEY not set")
    """

    def __init__(self, *, dotenv_paths: Iterable[str | Path] | None = None) -> None:
        self._dotenv_cache: dict[str, str] = {}
        self._local_secrets_cache: dict[str, str] | None = None
        if dotenv_paths is not None:
            for p in dotenv_paths:
                self._load_dotenv(p)

    # ------------------------------------------------------------------ Public

    def resolve(
        self,
        key_name: str,
        *,
        explicit: str | None = None,
        search_paths: Iterable[str | Path] | None = None,
        alt_names: Iterable[str] = (),
    ) -> ResolvedKey | None:
        """Try all sources in priority order; first hit wins."""
        # 1. explicit
        if explicit:
            return ResolvedKey(value=explicit, source=APIKeySource.EXPLICIT, name=key_name)

        candidates: list[str] = [key_name, *alt_names]

        # 2. env
        for name in candidates:
            v = os.environ.get(name)
            if v:
                return ResolvedKey(value=v, source=APIKeySource.ENV, name=name)

        # 3. .env
        for name in candidates:
            v = self._from_dotenv(name, search_paths=search_paths)
            if v:
                return ResolvedKey(value=v, source=APIKeySource.DOTENV, name=name)

        # 4. local_secrets.py
        for name in candidates:
            v = self._from_local_secrets(name, search_paths=search_paths)
            if v:
                return ResolvedKey(value=v, source=APIKeySource.LOCAL_SECRETS, name=name)

        # 5. keyring (best-effort)
        for name in candidates:
            v = self._from_keyring(name)
            if v:
                return ResolvedKey(value=v, source=APIKeySource.KEYRING, name=name)

        return None

    # ------------------------------------------------------------------ Internals

    def _load_dotenv(self, path: str | Path) -> None:
        path = Path(path)
        if not path.is_file():
            return
        try:
            for line in path.read_text(encoding="utf-8").splitlines():
                line = line.strip()
                if not line or line.startswith("#"):
                    continue
                if "=" not in line:
                    continue
                k, v = line.split("=", 1)
                k = k.strip()
                v = v.strip().strip('"').strip("'")
                self._dotenv_cache[k] = v
        except Exception:
            log.exception("Failed to read .env at %s", path)

    def _from_dotenv(self, name: str, *, search_paths: Iterable[str | Path] | None) -> str | None:
        if name in self._dotenv_cache:
            return self._dotenv_cache[name]
        if search_paths:
            for p in search_paths:
                self._load_dotenv(Path(p) / ".env")
                if name in self._dotenv_cache:
                    return self._dotenv_cache[name]
        return None

    def _load_local_secrets(self, search_paths: Iterable[str | Path] | None) -> None:
        if self._local_secrets_cache is not None:
            return
        candidates: list[Path] = []
        for p in search_paths or [Path.cwd()]:
            base = Path(p)
            candidates.append(base / "local_secrets.py")
            candidates.append(base.parent / "local_secrets.py")
        for c in candidates:
            if not c.is_file():
                continue
            try:
                import importlib.util

                spec = importlib.util.spec_from_file_location("local_secrets", c)
                if not spec or not spec.loader:
                    continue
                mod = importlib.util.module_from_spec(spec)
                spec.loader.exec_module(mod)  # type: ignore[union-attr]
                cache: dict[str, str] = {}
                for attr in dir(mod):
                    if attr.startswith("_"):
                        continue
                    v = getattr(mod, attr, None)
                    if isinstance(v, str):
                        cache[attr] = v
                self._local_secrets_cache = cache
                return
            except Exception:
                log.exception("Failed to load local_secrets.py at %s", c)
                continue
        self._local_secrets_cache = {}

    def _from_local_secrets(
        self, name: str, *, search_paths: Iterable[str | Path] | None
    ) -> str | None:
        self._load_local_secrets(search_paths)
        return (self._local_secrets_cache or {}).get(name)

    def _from_keyring(self, name: str) -> str | None:
        try:
            import keyring  # type: ignore[import-not-found]
        except ImportError:
            return None
        try:
            return keyring.get_password("forge-agent", name)
        except Exception:
            log.debug("keyring lookup failed for %s", name, exc_info=True)
            return None
