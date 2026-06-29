"""DatasetRegistry — global registry for dataset discovery and loading.

Provides a unified interface to access datasets from multiple stores.

Usage::

    from forge_agent.datasets.registry import get_registry

    registry = get_registry()
    registry.register_store("local", LocalDatasetStore(Path("./datasets")))
    registry.register_store("sqlite", SQLiteDatasetStore(Path("./datasets.db")))

    # List all datasets across all stores
    names = registry.list_all()

    # Load a dataset (searches all stores)
    ds = registry.load("product_examples")
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

from forge_agent.datasets import Dataset
from forge_agent.datasets.store import DatasetStore, LocalDatasetStore, SQLiteDatasetStore

log = logging.getLogger(__name__)


class DatasetRegistry:
    """Global registry for dataset stores.

    Manages multiple dataset stores and provides unified access to all datasets.
    """

    _instance: DatasetRegistry | None = None

    def __new__(cls) -> DatasetRegistry:
        if cls._instance is None:
            inst = super().__new__(cls)
            inst._stores: dict[str, DatasetStore] = {}
            cls._instance = inst
        return cls._instance

    @classmethod
    def reset_instance(cls) -> None:
        """Reset the singleton (useful for tests)."""
        cls._instance = None

    def register_store(self, name: str, store: DatasetStore) -> None:
        """Register a dataset store with a name.

        Args:
            name: Store identifier (e.g., "local", "sqlite")
            store: DatasetStore instance
        """
        self._stores[name] = store
        log.debug("Registered dataset store: %s", name)

    def unregister_store(self, name: str) -> bool:
        """Unregister a store. Returns True if removed."""
        if name in self._stores:
            del self._stores[name]
            log.debug("Unregistered dataset store: %s", name)
            return True
        return False

    def get_store(self, name: str) -> DatasetStore | None:
        """Get a registered store by name."""
        return self._stores.get(name)

    def list_stores(self) -> list[str]:
        """List all registered store names."""
        return list(self._stores.keys())

    def list_all(self) -> list[dict[str, Any]]:
        """List all datasets across all stores.

        Returns:
            List of dicts with 'name' and 'store' keys
        """
        results = []
        for store_name, store in self._stores.items():
            try:
                for ds_name in store.list():
                    results.append({"name": ds_name, "store": store_name})
            except Exception as exc:
                log.warning("Failed to list datasets from store '%s': %s", store_name, exc)
        return results

    def load(self, name: str, *, store_name: str | None = None) -> Dataset | None:
        """Load a dataset by name.

        Args:
            name: Dataset name
            store_name: Optional specific store to load from

        Returns:
            Dataset if found, None otherwise
        """
        if store_name:
            store = self._stores.get(store_name)
            if store:
                return store.load(name)
            return None

        # Search all stores
        for store in self._stores.values():
            ds = store.load(name)
            if ds is not None:
                return ds
        return None

    def save(self, dataset: Dataset, *, store_name: str | None = None) -> bool:
        """Save a dataset to a store.

        Args:
            dataset: Dataset to save
            store_name: Store to save to (defaults to first registered store)

        Returns:
            True if saved successfully
        """
        if store_name:
            store = self._stores.get(store_name)
            if not store:
                log.error("Store '%s' not found", store_name)
                return False
        else:
            if not self._stores:
                log.error("No stores registered")
                return False
            store = next(iter(self._stores.values()))

        try:
            store.save(dataset)
            return True
        except Exception as exc:
            log.error("Failed to save dataset '%s': %s", dataset.name, exc)
            return False

    def delete(self, name: str, *, store_name: str | None = None) -> bool:
        """Delete a dataset.

        Args:
            name: Dataset name
            store_name: Optional specific store to delete from

        Returns:
            True if deleted from any store
        """
        if store_name:
            store = self._stores.get(store_name)
            if store:
                return store.delete(name)
            return False

        # Delete from all stores
        deleted = False
        for store in self._stores.values():
            if store.delete(name):
                deleted = True
        return deleted


def get_registry() -> DatasetRegistry:
    """Get the global DatasetRegistry singleton."""
    return DatasetRegistry()


def setup_default_registry(
    local_path: Path | str | None = None,
    sqlite_path: Path | str | None = None,
) -> DatasetRegistry:
    """Setup registry with default stores.

    Args:
        local_path: Path for LocalDatasetStore (optional)
        sqlite_path: Path for SQLiteDatasetStore (optional)

    Returns:
        Configured DatasetRegistry
    """
    registry = get_registry()

    if local_path:
        registry.register_store("local", LocalDatasetStore(local_path))

    if sqlite_path:
        registry.register_store("sqlite", SQLiteDatasetStore(sqlite_path))

    return registry
