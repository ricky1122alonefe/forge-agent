"""Data parsers for different source types.

Handles HTML (BeautifulSoup), JSON API, and RSS feed parsing.
"""

from __future__ import annotations

import hashlib
import json
import re
from typing import Any

from forge_agent.scraper.config import FieldDef


def parse_html(html: str, fields: list[FieldDef]) -> dict[str, Any]:
    """Parse HTML using BeautifulSoup and CSS selectors.

    Args:
        html: Raw HTML content
        fields: List of FieldDef with CSS selectors

    Returns:
        Dictionary of extracted field values
    """
    try:
        from bs4 import BeautifulSoup
    except ImportError:
        raise ImportError(
            "beautifulsoup4 is required for HTML parsing. Install with: pip install beautifulsoup4"
        )

    soup = BeautifulSoup(html, "html.parser")
    result: dict[str, Any] = {}

    for field_def in fields:
        if not field_def.selector:
            continue

        elements = soup.select(field_def.selector)

        if not elements:
            result[field_def.name] = field_def.default
            continue

        # Extract text or attribute
        if len(elements) == 1:
            value = _extract_value(elements[0], field_def)
        else:
            # Multiple elements: return list
            value = [_extract_value(el, field_def) for el in elements]

        # Apply transform
        value = _apply_transform(value, field_def)
        result[field_def.name] = value

    return result


def _extract_value(element: Any, field_def: FieldDef) -> Any:
    """Extract value from a BeautifulSoup element."""
    # Check if selector targets an attribute (e.g., "a[href]")
    if "[" in field_def.selector and "]" in field_def.selector:
        attr_match = re.search(r"\[(\w+)\]", field_def.selector)
        if attr_match:
            attr_name = attr_match.group(1)
            return element.get(attr_name, field_def.default)

    # Default: extract text
    return element.get_text(strip=True)


def parse_json(data: dict | list, fields: list[FieldDef]) -> dict[str, Any]:
    """Parse JSON data using JSONPath-like selectors.

    Args:
        data: Parsed JSON data (dict or list)
        fields: List of FieldDef with JSONPath selectors

    Returns:
        Dictionary of extracted field values
    """
    result: dict[str, Any] = {}

    for field_def in fields:
        if not field_def.selector:
            continue

        value = _jsonpath_extract(data, field_def.selector)

        value = field_def.default if value is None else _apply_transform(value, field_def)

        result[field_def.name] = value

    return result


def _jsonpath_extract(data: Any, path: str) -> Any:
    """Simple JSONPath-like extraction.

    Supports:
    - "field" -> data["field"]
    - "field.subfield" -> data["field"]["subfield"]
    - "array[0]" -> data["array"][0]
    - "array[*].field" -> [item["field"] for item in data["array"]]
    """
    parts = path.split(".")
    current = data

    for part in parts:
        if current is None:
            return None

        # Handle array indexing: "field[0]" or "field[*]"
        if "[" in part and "]" in part:
            field_name, index_str = part.split("[", 1)
            index_str = index_str.rstrip("]")

            if field_name:
                current = current.get(field_name) if isinstance(current, dict) else None

            if current is None:
                return None

            if index_str == "*":
                # Wildcard: return list of all items
                if isinstance(current, list):
                    return current
                return None
            else:
                # Specific index
                try:
                    index = int(index_str)
                    if isinstance(current, list) and 0 <= index < len(current):
                        current = current[index]
                    else:
                        return None
                except ValueError:
                    return None
        else:
            # Regular field
            if isinstance(current, dict):
                current = current.get(part)
            else:
                return None

    return current


def parse_rss(xml_content: str, fields: list[FieldDef]) -> list[dict[str, Any]]:
    """Parse RSS/Atom feed.

    Args:
        xml_content: Raw XML content
        fields: List of FieldDef (optional, extracts all items if empty)

    Returns:
        List of item dictionaries
    """
    try:
        import xml.etree.ElementTree as ElementTree
    except ImportError:
        raise ImportError("xml.etree.ElementTree is required for RSS parsing")

    root = ElementTree.fromstring(xml_content)
    items = []

    # Handle both RSS and Atom formats
    # RSS: <channel><item>...</item></channel>
    # Atom: <entry>...</entry>

    # Try RSS format first
    for item in root.findall(".//item"):
        entry = _parse_rss_item(item)
        items.append(entry)

    # Try Atom format if no RSS items found
    if not items:
        namespaces = {"atom": "http://www.w3.org/2005/Atom"}
        for entry in root.findall(".//atom:entry", namespaces):
            entry_data = _parse_atom_entry(entry, namespaces)
            items.append(entry_data)

    # Apply field filters if specified
    if fields:
        filtered = []
        for item in items:
            filtered_item = {}
            for field_def in fields:
                value = item.get(field_def.name, field_def.default)
                filtered_item[field_def.name] = value
            filtered.append(filtered_item)
        return filtered

    return items


def _parse_rss_item(item: Any) -> dict[str, Any]:
    """Parse a single RSS <item> element."""
    return {
        "title": _get_text(item, "title"),
        "link": _get_text(item, "link"),
        "description": _get_text(item, "description"),
        "pubDate": _get_text(item, "pubDate"),
        "guid": _get_text(item, "guid"),
    }


def _parse_atom_entry(entry: Any, namespaces: dict) -> dict[str, Any]:
    """Parse a single Atom <entry> element."""
    title = entry.find("atom:title", namespaces)
    link = entry.find("atom:link", namespaces)
    summary = entry.find("atom:summary", namespaces)
    updated = entry.find("atom:updated", namespaces)
    entry_id = entry.find("atom:id", namespaces)

    return {
        "title": title.text if title is not None else "",
        "link": link.get("href", "") if link is not None else "",
        "description": summary.text if summary is not None else "",
        "pubDate": updated.text if updated is not None else "",
        "guid": entry_id.text if entry_id is not None else "",
    }


def _get_text(element: Any, tag: str) -> str:
    """Get text content of a child element."""
    child = element.find(tag)
    return child.text if child is not None and child.text else ""


def _apply_transform(value: Any, field_def: FieldDef) -> Any:
    """Apply transformation to extracted value."""
    if not field_def.transform or value is None:
        return value

    transforms = [t.strip() for t in field_def.transform.split(",")]

    for transform in transforms:
        if transform == "strip" and isinstance(value, str):
            value = value.strip()
        elif transform == "lower" and isinstance(value, str):
            value = value.lower()
        elif transform == "upper" and isinstance(value, str):
            value = value.upper()
        elif transform == "float":
            try:
                value = float(value)
            except (ValueError, TypeError):
                value = field_def.default
        elif transform == "int":
            try:
                value = int(float(value))
            except (ValueError, TypeError):
                value = field_def.default
        elif transform == "bool":
            value = bool(value)

    return value


def compute_checksum(data: dict[str, Any]) -> str:
    """Compute checksum for deduplication."""
    # Sort keys for consistent hashing
    data_str = json.dumps(data, sort_keys=True, ensure_ascii=False)
    return hashlib.md5(data_str.encode()).hexdigest()
