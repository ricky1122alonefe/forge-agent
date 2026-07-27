"""Smoke tests for the scraper module (S2 safety net).

Covers config construction, JSON parsing, checksum, and store
integration — without hitting the network.
"""

from __future__ import annotations

from forge_agent.scraper.config import AuthType, FieldDef, ScraperConfig, SourceType
from forge_agent.scraper.parser import compute_checksum, parse_json
from forge_agent.storage import ForgeStore


class TestConfig:
    def test_source_type_enum(self) -> None:
        assert SourceType.HTML.value == "html"
        assert SourceType.JSON_API.value == "json_api"
        assert SourceType.RSS.value == "rss"

    def test_auth_type_enum(self) -> None:
        assert AuthType.NONE.value == "none"
        assert AuthType.BEARER_TOKEN.value == "bearer_token"

    def test_field_def_construction(self) -> None:
        fd = FieldDef(name="title", selector=".title", type="str", required=True)
        assert fd.name == "title"
        assert fd.selector == ".title"

    def test_field_def_roundtrip(self) -> None:
        fd = FieldDef(name="price", selector=".price", type="float", default=0.0)
        d = fd.to_dict()
        restored = FieldDef.from_dict(d)
        assert restored.name == "price"
        assert restored.type == "float"
        assert restored.default == 0.0

    def test_scraper_config_construction(self) -> None:
        config = ScraperConfig(
            agent_id="test.scraper",
            name="Test Scraper",
            source_type=SourceType.JSON_API,
            urls=["https://example.com/api"],
            fields=[FieldDef(name="count", selector="data.count", type="int")],
        )
        assert config.agent_id == "test.scraper"
        assert config.source_type == SourceType.JSON_API
        assert len(config.urls) == 1
        assert len(config.fields) == 1


class TestJsonParser:
    def test_simple_field_extraction(self) -> None:
        data = {"name": "labubu", "price": 99.9}
        fields = [
            FieldDef(name="name", selector="name"),
            FieldDef(name="price", selector="price", type="float"),
        ]
        result = parse_json(data, fields)
        assert result["name"] == "labubu"
        assert result["price"] == 99.9

    def test_nested_field_extraction(self) -> None:
        data = {"data": {"count": 42, "items": [{"id": 1}, {"id": 2}]}}
        fields = [
            FieldDef(name="count", selector="data.count", type="int"),
            FieldDef(name="first_id", selector="data.items[0].id", type="int"),
        ]
        result = parse_json(data, fields)
        assert result["count"] == 42
        assert result["first_id"] == 1

    def test_missing_field_uses_default(self) -> None:
        data = {"name": "x"}
        fields = [FieldDef(name="missing", selector="nonexistent", default="N/A")]
        result = parse_json(data, fields)
        assert result["missing"] == "N/A"

    def test_wildcard_array_returns_full_items(self) -> None:
        """items[*] returns the array; .id suffix is not applied per-element
        (JSONPath limitation — use items[0].id for a single value)."""
        data = {"items": [{"id": 1}, {"id": 2}, {"id": 3}]}
        fields = [FieldDef(name="all_items", selector="items[*]")]
        result = parse_json(data, fields)
        assert result["all_items"] == [{"id": 1}, {"id": 2}, {"id": 3}]

    def test_indexed_array_field(self) -> None:
        data = {"items": [{"id": 1}, {"id": 2}, {"id": 3}]}
        fields = [FieldDef(name="first_id", selector="items[0].id", type="int")]
        result = parse_json(data, fields)
        assert result["first_id"] == 1


class TestChecksum:
    def test_checksum_deterministic(self) -> None:
        data = {"a": 1, "b": 2}
        c1 = compute_checksum(data)
        c2 = compute_checksum({"b": 2, "a": 1})  # different key order
        assert c1 == c2  # sort_keys makes it order-independent

    def test_checksum_differs_for_different_data(self) -> None:
        assert compute_checksum({"a": 1}) != compute_checksum({"a": 2})


class TestStoreIntegration:
    def test_store_insert_and_query(self, tmp_path) -> None:
        store = ForgeStore(db_path=tmp_path / "test_scraper.db")
        record = store.insert(
            agent_id="test.scraper",
            data={"title": "hello", "count": 5},
            category="scraped",
            tags=["test"],
        )
        assert record.id is not None

        records = store.query(agent_id="test.scraper", category="scraped")
        assert len(records) >= 1
        found = records[0]
        assert found.data["title"] == "hello"
        assert found.agent_id == "test.scraper"

        store.close()
