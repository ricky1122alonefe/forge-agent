"""FilePromptStore — filesystem-backed prompt store with versioned files.

Layout::

    prompts/
        <agent_id>/
            v1.j2
            v2.j2
            v3.j2

Versioning is by file name (semver recommended). Rollback = swap active file.
This is intentionally minimal; production setups can back it with git.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from forge_agent.core.capabilities import PromptManagerProtocol


class FilePromptStore(PromptManagerProtocol):
    """Filesystem-backed prompt store.

    Args:
        root: Directory containing `prompts/<agent_id>/<version>.j2` files.
        meta_file: Optional JSON file mapping agent_id -> active version.
    """

    def __init__(self, root: str | Path, *, meta_file: str = "_active.json") -> None:
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)
        self.meta_file = self.root / meta_file
        self._active: dict[str, str] = self._load_meta()

    # ------------------------------------------------------------------ API

    def get(self, agent_id: str, *, version: str | None = None) -> str:
        version = version or self._active.get(agent_id)
        if not version:
            versions = self.list_versions(agent_id)
            if not versions:
                from forge_agent.exceptions import PromptNotFoundError
                raise PromptNotFoundError(agent_id)
            version = sorted(versions)[-1]
        path = self.root / agent_id / f"{version}.j2"
        if not path.is_file():
            from forge_agent.exceptions import PromptFileNotFoundError
            raise PromptFileNotFoundError(str(path))
        return path.read_text(encoding="utf-8")

    def render(
        self,
        agent_id: str,
        variables: dict[str, Any],
        *,
        version: str | None = None,
    ) -> str:
        template = self.get(agent_id, version=version)
        try:
            return template.format(**variables)
        except KeyError as exc:
            from forge_agent.exceptions import PromptVariableError
            raise PromptVariableError(agent_id, str(exc.args[0])) from exc

    def list_versions(self, agent_id: str) -> list[str]:
        d = self.root / agent_id
        if not d.is_dir():
            return []
        return sorted(p.stem for p in d.glob("*.j2"))

    def register(self, agent_id: str, version: str, template: str) -> None:
        d = self.root / agent_id
        d.mkdir(parents=True, exist_ok=True)
        (d / f"{version}.j2").write_text(template, encoding="utf-8")
        # Auto-activate if first version
        self._active.setdefault(agent_id, version)
        self._save_meta()

    def activate(self, agent_id: str, version: str) -> None:
        self._active[agent_id] = version
        self._save_meta()

    # ------------------------------------------------------------------ IO

    def _load_meta(self) -> dict[str, str]:
        if not self.meta_file.is_file():
            return {}
        try:
            return json.loads(self.meta_file.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            return {}

    def _save_meta(self) -> None:
        self.meta_file.write_text(
            json.dumps(self._active, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )
