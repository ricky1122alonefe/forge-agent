"""Dataset — structured data storage for few-shot examples and training data.

Datasets are used to provide context examples for LLM generation, especially
for scraper agents that need to understand data schemas.

Usage::

    from forge_agent.datasets import Dataset, DatasetItem

    ds = Dataset(
        name="product_examples",
        description="Sample product pages",
        items=[
            DatasetItem(
                input="https://example.com/product/123",
                output={"name": "Widget", "price": 29.99},
                metadata={"category": "electronics"},
            ),
        ],
    )

    # Add items
    ds.add_item(DatasetItem(input="...", output={...}))

    # Query
    items = ds.sample(n=5)
"""

from __future__ import annotations

import logging
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any

log = logging.getLogger(__name__)


@dataclass
class DatasetItem:
    """A single example in a dataset.

    Attributes:
        input: The input data (URL, query, prompt, etc.)
        output: The expected output (structured data, response, etc.)
        metadata: Optional metadata (tags, category, source, etc.)
        id: Unique identifier (auto-generated if not provided)
    """

    input: Any
    output: Any
    metadata: dict[str, Any] = field(default_factory=dict)
    id: str = ""

    def __post_init__(self) -> None:
        if not self.id:
            import uuid

            self.id = uuid.uuid4().hex[:12]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> DatasetItem:
        return cls(**{k: v for k, v in d.items() if k in cls.__dataclass_fields__})


@dataclass
class Dataset:
    """A collection of dataset items.

    Attributes:
        name: Dataset name (unique identifier)
        description: Human-readable description
        items: List of dataset items
        tags: Optional tags for categorization
        created_at: ISO8601 timestamp
        updated_at: ISO8601 timestamp
        version: Dataset version string
    """

    name: str
    description: str = ""
    items: list[DatasetItem] = field(default_factory=list)
    tags: list[str] = field(default_factory=list)
    created_at: str = field(default_factory=lambda: _now())
    updated_at: str = field(default_factory=lambda: _now())
    version: str = "1.0"

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "description": self.description,
            "items": [item.to_dict() for item in self.items],
            "tags": self.tags,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "version": self.version,
        }

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> Dataset:
        items = [DatasetItem.from_dict(item) for item in d.get("items", [])]
        return cls(
            name=d["name"],
            description=d.get("description", ""),
            items=items,
            tags=d.get("tags", []),
            created_at=d.get("created_at", _now()),
            updated_at=d.get("updated_at", _now()),
            version=d.get("version", "1.0"),
        )

    def add_item(self, item: DatasetItem) -> None:
        """Add an item to the dataset."""
        self.items.append(item)
        self.updated_at = _now()

    def remove_item(self, item_id: str) -> bool:
        """Remove an item by ID. Returns True if removed."""
        original_len = len(self.items)
        self.items = [item for item in self.items if item.id != item_id]
        if len(self.items) < original_len:
            self.updated_at = _now()
            return True
        return False

    def get_item(self, item_id: str) -> DatasetItem | None:
        """Get an item by ID."""
        for item in self.items:
            if item.id == item_id:
                return item
        return None

    def sample(self, n: int = 5, *, seed: int | None = None) -> list[DatasetItem]:
        """Get a random sample of items.

        Args:
            n: Number of items to sample
            seed: Optional random seed for reproducibility

        Returns:
            List of sampled items (or all items if n >= len(items))
        """
        import random

        if seed is not None:
            random.seed(seed)
        if n >= len(self.items):
            return list(self.items)
        return random.sample(self.items, n)

    def filter_by_tag(self, tag: str) -> list[DatasetItem]:
        """Get items that have a specific tag in their metadata."""
        return [item for item in self.items if tag in item.metadata.get("tags", [])]

    def __len__(self) -> int:
        return len(self.items)

    def __iter__(self):
        return iter(self.items)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()
