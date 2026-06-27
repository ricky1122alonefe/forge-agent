"""PromptManager — re-export of the default in-memory implementation.

For most cases the in-memory manager is fine. For production, swap in
FilePromptStore (filesystem + git) or implement DBPromptStore.
"""

from __future__ import annotations

from forge_agent.core.capabilities import InMemoryPromptManager as _Default

# Public re-export
PromptManager = _Default
InMemoryPromptManager = _Default
