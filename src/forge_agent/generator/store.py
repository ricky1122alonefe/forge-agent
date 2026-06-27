"""CodeStore — persistent storage for generated Agent code.

Default implementation: filesystem, layout::

    generated_agents/
        MANIFEST.json
        <agent_id>/
            v1.py
            v1.meta.json
            v2.py
            v2.meta.json

Rules:
    - One folder per agent_id.
    - Versions are sequential (v1, v2, v3...).
    - v1.meta.json MUST exist alongside v1.py.
    - No auto-deletion of old versions.
    - Activate is a separate action from save.
"""

from __future__ import annotations

import hashlib
import logging
import re
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from forge_agent.generator.manifest import AgentManifestEntry, AgentVersionMeta, Manifest

log = logging.getLogger(__name__)


def _hash_code(source: str) -> str:
    return "sha256:" + hashlib.sha256(source.encode("utf-8")).hexdigest()[:16]


def _next_version(existing: list[str]) -> str:
    nums = []
    for v in existing:
        m = re.match(r"^v(\d+)$", v)
        if m:
            nums.append(int(m.group(1)))
    return f"v{(max(nums) if nums else 0) + 1}"


@dataclass
class SavedCode:
    """Result of saving a new version."""

    agent_id: str
    version: str
    code_path: Path
    meta_path: Path
    code_hash: str
    is_new_agent: bool


class FileCodeStore:
    """Filesystem-backed code store with manifest coordination."""

    def __init__(self, root: Path | str) -> None:
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)
        self.manifest_path = self.root / "MANIFEST.json"
        self._manifest = Manifest.load(self.manifest_path)
        if not self._manifest.project:
            # Try to infer from the directory name
            self._manifest.project = self.root.resolve().parent.name or "my_app"

    # ------------------------------------------------------------------ Manifest

    @property
    def manifest(self) -> Manifest:
        return self._manifest

    def flush_manifest(self) -> None:
        """Write the in-memory manifest to disk."""
        self._manifest.save(self.manifest_path)

    # ------------------------------------------------------------------ Save

    def save(
        self,
        agent_id: str,
        source: str,
        *,
        requirement: str = "",
        created_by: str = "user",
        llm_provider: str | None = None,
        llm_model: str | None = None,
        validation_status: str = "unknown",
        validation_errors: list[str] | None = None,
        smoke_test_status: str = "unknown",
        smoke_test_error: str | None = None,
        agent_type: str = "",
    ) -> SavedCode:
        """Save a new version. If agent_id is new, creates v1; else v(N+1).

        Old versions are NEVER overwritten.
        """
        agent_dir = self.root / agent_id
        agent_dir.mkdir(parents=True, exist_ok=True)

        entry = self._manifest.agents.get(agent_id)
        is_new_agent = entry is None
        if entry is None:
            entry = AgentManifestEntry(
                agent_id=agent_id,
                created_at=_now_iso(),
                active_version="",  # not yet active
                versions=[],
                agent_type=agent_type,
            )
            self._manifest.agents[agent_id] = entry

        existing_versions = [v.version for v in entry.versions]
        version = _next_version(existing_versions)
        supersedes = entry.active_version if entry.active_version else None

        code_hash = _hash_code(source)
        code_path = agent_dir / f"{version}.py"
        meta_path = agent_dir / f"{version}.meta.json"

        # Write code
        code_path.write_text(source, encoding="utf-8")

        # Write meta
        meta = AgentVersionMeta(
            version=version,
            created_at=_now_iso(),
            created_by=created_by,
            requirement=requirement,
            llm_provider=llm_provider,
            llm_model=llm_model,
            validation_status=validation_status,
            validation_errors=validation_errors or [],
            smoke_test_status=smoke_test_status,
            smoke_test_error=smoke_test_error,
            code_hash=code_hash,
            code_path=str(code_path.relative_to(self.root)),
            supersedes=supersedes,
        )
        meta_path.write_text(
            __import__("json").dumps(meta.to_dict(), indent=2, ensure_ascii=False),
            encoding="utf-8",
        )
        entry.versions.append(meta)

        # Auto-activate only when this is a new agent (first version of a brand-new agent).
        # Subsequent versions on existing agents are NOT auto-activated — the user
        # must explicitly run `forge-agent use` to switch.
        if is_new_agent:
            entry.active_version = version

        self.flush_manifest()
        return SavedCode(
            agent_id=agent_id,
            version=version,
            code_path=code_path,
            meta_path=meta_path,
            code_hash=code_hash,
            is_new_agent=is_new_agent,
        )

    # ------------------------------------------------------------------ Load

    def load(self, agent_id: str, version: str | None = None) -> str | None:
        """Load source code. Default: active version."""
        entry = self._manifest.agents.get(agent_id)
        if not entry:
            return None
        ver = version or entry.active_version
        meta = entry.get_version(ver)
        if not meta or not meta.code_path:
            return None
        path = self.root / meta.code_path
        if not path.is_file():
            return None
        return path.read_text(encoding="utf-8")

    def list_versions(self, agent_id: str) -> list[str]:
        entry = self._manifest.agents.get(agent_id)
        if not entry:
            return []
        return [v.version for v in entry.versions]

    def get_meta(self, agent_id: str, version: str | None = None) -> AgentVersionMeta | None:
        entry = self._manifest.agents.get(agent_id)
        if not entry:
            return None
        return entry.get_version(version or entry.active_version)

    # ------------------------------------------------------------------ Activation

    def activate(self, agent_id: str, version: str) -> None:
        entry = self._manifest.agents.get(agent_id)
        if not entry:
            raise KeyError(f"Agent {agent_id!r} not in manifest")
        if not entry.get_version(version):
            raise KeyError(f"Version {version!r} of {agent_id!r} not found")
        entry.active_version = version
        self.flush_manifest()

    def rollback(self, agent_id: str) -> str:
        """Roll back to the previous version. Returns the new active version."""
        entry = self._manifest.agents.get(agent_id)
        if not entry:
            raise KeyError(f"Agent {agent_id!r} not in manifest")
        versions = entry.versions
        if len(versions) < 2:
            raise ValueError(f"Agent {agent_id!r} has no previous version to roll back to")
        current_idx = next(
            (i for i, v in enumerate(versions) if v.version == entry.active_version),
            None,
        )
        if current_idx is None or current_idx == 0:
            raise ValueError(f"Agent {agent_id!r} is at its earliest version")
        new_active = versions[current_idx - 1].version
        entry.active_version = new_active
        self.flush_manifest()
        return new_active

    # ------------------------------------------------------------------ Archive

    def archive(self, agent_id: str) -> None:
        if agent_id not in self._manifest.agents:
            return
        if agent_id not in self._manifest.archive:
            self._manifest.archive.append(agent_id)
        # Keep entry in manifest (for audit), but mark deprecated
        for v in self._manifest.agents[agent_id].versions:
            v.deprecated = True
            v.deprecated_reason = v.deprecated_reason or "agent archived"
        self.flush_manifest()

    def delete_version(self, agent_id: str, version: str) -> None:
        entry = self._manifest.agents.get(agent_id)
        if not entry:
            return
        if len(entry.versions) <= 1:
            raise ValueError(
                f"Cannot delete the only version of {agent_id!r}; archive the whole agent instead"
            )
        entry.versions = [v for v in entry.versions if v.version != version]
        if entry.active_version == version:
            entry.active_version = entry.versions[-1].version
        # Delete files
        for suffix in (".py", ".meta.json"):
            p = self.root / agent_id / f"{version}{suffix}"
            if p.is_file():
                p.unlink()
        self.flush_manifest()


def _now_iso() -> str:
    from datetime import datetime, timezone
    return datetime.now(timezone.utc).isoformat()
