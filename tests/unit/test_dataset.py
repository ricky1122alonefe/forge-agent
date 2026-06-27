"""Tests for T2.2 — Dataset module."""

from __future__ import annotations

import shutil
import tempfile
from pathlib import Path

import pytest

from forge_agent.datasets import Dataset, DatasetItem
from forge_agent.datasets.registry import DatasetRegistry, get_registry, setup_default_registry
from forge_agent.datasets.store import LocalDatasetStore, SQLiteDatasetStore


# ------------------------------------------------------------------ DatasetItem

class TestDatasetItem:
    def test_basic_creation(self):
        item = DatasetItem(input="test input", output={"result": "ok"})
        assert item.input == "test input"
        assert item.output == {"result": "ok"}
        assert item.id  # Auto-generated

    def test_custom_id(self):
        item = DatasetItem(input="test", output="result", id="custom-id")
        assert item.id == "custom-id"

    def test_metadata(self):
        item = DatasetItem(
            input="test",
            output="result",
            metadata={"tags": ["example"], "source": "web"},
        )
        assert item.metadata["tags"] == ["example"]
        assert item.metadata["source"] == "web"

    def test_to_dict(self):
        item = DatasetItem(input="test", output="result", id="item-1")
        d = item.to_dict()
        assert d["input"] == "test"
        assert d["output"] == "result"
        assert d["id"] == "item-1"

    def test_from_dict(self):
        d = {"input": "test", "output": "result", "id": "item-1", "metadata": {}}
        item = DatasetItem.from_dict(d)
        assert item.input == "test"
        assert item.id == "item-1"


# ------------------------------------------------------------------ Dataset

class TestDataset:
    def test_basic_creation(self):
        ds = Dataset(name="test_ds", description="Test dataset")
        assert ds.name == "test_ds"
        assert ds.description == "Test dataset"
        assert len(ds.items) == 0

    def test_add_item(self):
        ds = Dataset(name="test_ds")
        item = DatasetItem(input="test", output="result")
        ds.add_item(item)
        assert len(ds.items) == 1
        assert ds.items[0].input == "test"

    def test_remove_item(self):
        ds = Dataset(name="test_ds")
        item = DatasetItem(input="test", output="result", id="item-1")
        ds.add_item(item)
        assert ds.remove_item("item-1") is True
        assert len(ds.items) == 0

    def test_remove_nonexistent(self):
        ds = Dataset(name="test_ds")
        assert ds.remove_item("nonexistent") is False

    def test_get_item(self):
        ds = Dataset(name="test_ds")
        item = DatasetItem(input="test", output="result", id="item-1")
        ds.add_item(item)
        found = ds.get_item("item-1")
        assert found is not None
        assert found.input == "test"

    def test_sample(self):
        ds = Dataset(name="test_ds")
        for i in range(10):
            ds.add_item(DatasetItem(input=f"test-{i}", output=f"result-{i}"))
        sample = ds.sample(n=3, seed=42)
        assert len(sample) == 3

    def test_sample_more_than_available(self):
        ds = Dataset(name="test_ds")
        ds.add_item(DatasetItem(input="test", output="result"))
        sample = ds.sample(n=10)
        assert len(sample) == 1

    def test_filter_by_tag(self):
        ds = Dataset(name="test_ds")
        ds.add_item(DatasetItem(input="test1", output="result1", metadata={"tags": ["web"]}))
        ds.add_item(DatasetItem(input="test2", output="result2", metadata={"tags": ["api"]}))
        ds.add_item(DatasetItem(input="test3", output="result3", metadata={"tags": ["web", "api"]}))
        web_items = ds.filter_by_tag("web")
        assert len(web_items) == 2

    def test_to_dict(self):
        ds = Dataset(name="test_ds", description="Test", tags=["example"])
        ds.add_item(DatasetItem(input="test", output="result"))
        d = ds.to_dict()
        assert d["name"] == "test_ds"
        assert d["description"] == "Test"
        assert len(d["items"]) == 1

    def test_from_dict(self):
        d = {
            "name": "test_ds",
            "description": "Test",
            "items": [{"input": "test", "output": "result", "id": "item-1", "metadata": {}}],
            "tags": ["example"],
        }
        ds = Dataset.from_dict(d)
        assert ds.name == "test_ds"
        assert len(ds.items) == 1

    def test_len(self):
        ds = Dataset(name="test_ds")
        assert len(ds) == 0
        ds.add_item(DatasetItem(input="test", output="result"))
        assert len(ds) == 1

    def test_iter(self):
        ds = Dataset(name="test_ds")
        ds.add_item(DatasetItem(input="test1", output="result1"))
        ds.add_item(DatasetItem(input="test2", output="result2"))
        items = list(ds)
        assert len(items) == 2


# ------------------------------------------------------------------ LocalDatasetStore

class TestLocalDatasetStore:
    def setup_method(self):
        self.tmpdir = Path(tempfile.mkdtemp())

    def teardown_method(self):
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def test_save_and_load(self):
        store = LocalDatasetStore(self.tmpdir)
        ds = Dataset(name="test_ds", description="Test")
        ds.add_item(DatasetItem(input="test", output="result"))
        store.save(ds)
        loaded = store.load("test_ds")
        assert loaded is not None
        assert loaded.name == "test_ds"
        assert len(loaded.items) == 1

    def test_load_nonexistent(self):
        store = LocalDatasetStore(self.tmpdir)
        assert store.load("nonexistent") is None

    def test_delete(self):
        store = LocalDatasetStore(self.tmpdir)
        ds = Dataset(name="test_ds")
        store.save(ds)
        assert store.delete("test_ds") is True
        assert store.load("test_ds") is None

    def test_delete_nonexistent(self):
        store = LocalDatasetStore(self.tmpdir)
        assert store.delete("nonexistent") is False

    def test_list(self):
        store = LocalDatasetStore(self.tmpdir)
        store.save(Dataset(name="ds1"))
        store.save(Dataset(name="ds2"))
        names = store.list()
        assert "ds1" in names
        assert "ds2" in names

    def test_exists(self):
        store = LocalDatasetStore(self.tmpdir)
        store.save(Dataset(name="test_ds"))
        assert store.exists("test_ds") is True
        assert store.exists("nonexistent") is False


# ------------------------------------------------------------------ SQLiteDatasetStore

class TestSQLiteDatasetStore:
    def setup_method(self):
        self.tmpdir = Path(tempfile.mkdtemp())

    def teardown_method(self):
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def test_save_and_load(self):
        store = SQLiteDatasetStore(self.tmpdir / "test.db")
        ds = Dataset(name="test_ds", description="Test", tags=["example"])
        ds.add_item(DatasetItem(input="test", output={"result": "ok"}))
        store.save(ds)
        loaded = store.load("test_ds")
        assert loaded is not None
        assert loaded.name == "test_ds"
        assert loaded.tags == ["example"]
        assert len(loaded.items) == 1
        store.close()

    def test_load_nonexistent(self):
        store = SQLiteDatasetStore(self.tmpdir / "test.db")
        assert store.load("nonexistent") is None
        store.close()

    def test_delete(self):
        store = SQLiteDatasetStore(self.tmpdir / "test.db")
        store.save(Dataset(name="test_ds"))
        assert store.delete("test_ds") is True
        assert store.load("test_ds") is None
        store.close()

    def test_list(self):
        store = SQLiteDatasetStore(self.tmpdir / "test.db")
        store.save(Dataset(name="ds1"))
        store.save(Dataset(name="ds2"))
        names = store.list()
        assert "ds1" in names
        assert "ds2" in names
        store.close()

    def test_exists(self):
        store = SQLiteDatasetStore(self.tmpdir / "test.db")
        store.save(Dataset(name="test_ds"))
        assert store.exists("test_ds") is True
        assert store.exists("nonexistent") is False
        store.close()

    def test_update_dataset(self):
        store = SQLiteDatasetStore(self.tmpdir / "test.db")
        ds = Dataset(name="test_ds", description="v1")
        ds.add_item(DatasetItem(input="test1", output="result1"))
        store.save(ds)
        ds.description = "v2"
        ds.add_item(DatasetItem(input="test2", output="result2"))
        store.save(ds)
        loaded = store.load("test_ds")
        assert loaded.description == "v2"
        assert len(loaded.items) == 2
        store.close()


# ------------------------------------------------------------------ DatasetRegistry

class TestDatasetRegistry:
    def setup_method(self):
        DatasetRegistry.reset_instance()
        self.tmpdir = Path(tempfile.mkdtemp())

    def teardown_method(self):
        shutil.rmtree(self.tmpdir, ignore_errors=True)
        DatasetRegistry.reset_instance()

    def test_register_store(self):
        registry = get_registry()
        store = LocalDatasetStore(self.tmpdir)
        registry.register_store("local", store)
        assert "local" in registry.list_stores()

    def test_unregister_store(self):
        registry = get_registry()
        registry.register_store("local", LocalDatasetStore(self.tmpdir))
        assert registry.unregister_store("local") is True
        assert "local" not in registry.list_stores()

    def test_list_all(self):
        registry = get_registry()
        store1 = LocalDatasetStore(self.tmpdir / "store1")
        store2 = LocalDatasetStore(self.tmpdir / "store2")
        store1.save(Dataset(name="ds1"))
        store2.save(Dataset(name="ds2"))
        registry.register_store("store1", store1)
        registry.register_store("store2", store2)
        all_ds = registry.list_all()
        assert len(all_ds) == 2
        names = [d["name"] for d in all_ds]
        assert "ds1" in names
        assert "ds2" in names

    def test_load_from_specific_store(self):
        registry = get_registry()
        store = LocalDatasetStore(self.tmpdir)
        store.save(Dataset(name="test_ds"))
        registry.register_store("local", store)
        loaded = registry.load("test_ds", store_name="local")
        assert loaded is not None
        assert loaded.name == "test_ds"

    def test_load_from_any_store(self):
        registry = get_registry()
        store = LocalDatasetStore(self.tmpdir)
        store.save(Dataset(name="test_ds"))
        registry.register_store("local", store)
        loaded = registry.load("test_ds")
        assert loaded is not None

    def test_save_to_specific_store(self):
        registry = get_registry()
        store = LocalDatasetStore(self.tmpdir)
        registry.register_store("local", store)
        ds = Dataset(name="test_ds")
        assert registry.save(ds, store_name="local") is True
        assert store.exists("test_ds")

    def test_delete_from_specific_store(self):
        registry = get_registry()
        store = LocalDatasetStore(self.tmpdir)
        store.save(Dataset(name="test_ds"))
        registry.register_store("local", store)
        assert registry.delete("test_ds", store_name="local") is True
        assert not store.exists("test_ds")

    def test_setup_default_registry(self):
        registry = setup_default_registry(
            local_path=self.tmpdir / "local",
            sqlite_path=self.tmpdir / "sqlite.db",
        )
        assert "local" in registry.list_stores()
        assert "sqlite" in registry.list_stores()
