"""Keyword-based local knowledge searcher (very simple, but real)."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from forge_agent.core.capabilities import SearcherProtocol

_TOKEN_RE = re.compile(r"[\w一-鿿]+", re.UNICODE)


def _tokenize(text: str) -> list[str]:
    return [t.lower() for t in _TOKEN_RE.findall(text or "")]


class KeywordKnowledgeSearcher(SearcherProtocol):
    """Search across a directory of text/markdown files by keyword frequency.

    Replace with a vector searcher (FAISS, Qdrant) for production.
    """

    def __init__(self, corpus_dir: str | Path) -> None:
        self.root = Path(corpus_dir)
        self._docs: list[tuple[Path, list[str], str]] = []
        if self.root.is_dir():
            for p in self.root.rglob("*"):
                if p.is_file() and p.suffix in {".txt", ".md", ".rst"}:
                    text = p.read_text(encoding="utf-8", errors="ignore")
                    self._docs.append((p, _tokenize(text), text))

    async def search(self, query: str, *, top_k: int = 5, **kwargs: Any) -> list[dict[str, Any]]:
        q_tokens = _tokenize(query)
        if not q_tokens or not self._docs:
            return []
        scores: list[tuple[int, Path, str]] = []
        for path, tokens, text in self._docs:
            score = sum(1 for t in q_tokens if t in tokens)
            if score > 0:
                scores.append((score, path, text[:500]))
        scores.sort(key=lambda t: -t[0])
        return [
            {"path": str(p), "score": float(s), "snippet": snip} for s, p, snip in scores[:top_k]
        ]
