"""Domain schemas — standardized shapes for data that agents consume.

A SchemaRecord is the contract between the data layer and the analysis layer.
Different scrapers produce different raw shapes, but after normalization every
record must conform to a schema that agents understand.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class SchemaRecord:
    """Base class for normalized domain records.

    Attributes:
        source: Identifier of the data source (e.g. "odds.365").
        timestamp: ISO8601 timestamp when the data was fetched.
        raw: Original raw payload (kept for audit / debug).
        metadata: Extra source-specific fields.
    """

    source: str
    timestamp: str
    raw: dict[str, Any] = field(default_factory=dict)
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "source": self.source,
            "timestamp": self.timestamp,
            "raw": self.raw,
            "metadata": self.metadata,
        }

    def to_evidence(self) -> list[str]:
        """Convert the record into human-readable evidence strings."""
        return []


@dataclass
class OddsRecord(SchemaRecord):
    """Standardized odds record for a football match.

    All odds-related agents should consume this shape, regardless of which
    betting site provided the data.
    """

    home: str = ""
    away: str = ""
    home_odds: float | None = None
    away_odds: float | None = None
    draw_odds: float | None = None
    market: str = "1x2"  # e.g. "1x2", "asian_handicap", "over_under"

    def to_dict(self) -> dict[str, Any]:
        base = super().to_dict()
        base.update(
            {
                "home": self.home,
                "away": self.away,
                "home_odds": self.home_odds,
                "away_odds": self.away_odds,
                "draw_odds": self.draw_odds,
                "market": self.market,
            }
        )
        return base

    def to_evidence(self) -> list[str]:
        parts = [
            f"赔率来源：{self.source}",
            f"对阵：{self.home} vs {self.away}",
        ]
        if self.home_odds is not None:
            parts.append(f"{self.home} 胜赔 {self.home_odds}")
        if self.draw_odds is not None:
            parts.append(f"平局赔率 {self.draw_odds}")
        if self.away_odds is not None:
            parts.append(f"{self.away} 胜赔 {self.away_odds}")
        parts.append(f"采集时间：{self.timestamp}")
        return parts
