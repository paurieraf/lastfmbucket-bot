"""
Callback data protocol for Telegram inline keyboard buttons.

This module centralizes all callback handling:
- Action definitions (what button was pressed)
- Compact encoding/decoding (must fit in 64 bytes)
- Type-safe payload parsing

Format: "v|action|owner_id|entity|period"
Example: "1|t|123456789|a|w" = tops, user 123456789, artist, week
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import TYPE_CHECKING, Optional

if TYPE_CHECKING:
    import lastfm

SEP = "|"
VERSION = "1"


class Action(StrEnum):
    """Short codes for callback actions."""

    NP_LESS = "nl"
    NP_LESS_COVER = "nc"
    NP_MORE = "nm"
    PREF_UNLINK = "pu"
    TOPS = "t"


class Entity(StrEnum):
    """Short codes for top entity types."""

    ARTIST = "a"
    ALBUM = "b"
    TRACK = "t"


class Period(StrEnum):
    """Short codes for time periods."""

    WEEK = "w"
    MONTH_1 = "1"
    MONTH_3 = "3"
    MONTH_6 = "6"
    YEAR = "y"
    OVERALL = "o"


@dataclass(frozen=True, slots=True)
class Callback:
    """
    Typed representation of callback data.

    Encodes all information needed to handle a button press:
    - action: what to do
    - owner_id: the telegram user whose data to show (fixes the group bug)
    - entity/period: optional parameters for tops command
    """

    action: Action
    owner_id: int
    entity: Optional[Entity] = None
    period: Optional[Period] = None

    def encode(self) -> str:
        """Encode to compact string format for Telegram callback_data."""
        parts = [
            VERSION,
            self.action,
            str(self.owner_id),
            self.entity or "",
            self.period or "",
        ]
        encoded = SEP.join(parts)
        assert len(encoded.encode("utf-8")) <= 64, f"Callback too long: {encoded}"
        return encoded

    @classmethod
    def decode(cls, data: str) -> Optional[Callback]:
        """Decode callback data string to typed Callback object."""
        try:
            parts = data.split(SEP)
            if len(parts) < 3:
                return None

            version = parts[0]
            if version != VERSION:
                return None

            action = Action(parts[1])
            owner_id = int(parts[2])
            entity = Entity(parts[3]) if len(parts) > 3 and parts[3] else None
            period = Period(parts[4]) if len(parts) > 4 and parts[4] else None

            return cls(
                action=action,
                owner_id=owner_id,
                entity=entity,
                period=period,
            )
        except (ValueError, IndexError):
            return None

    def to_lastfm_entity(self) -> Optional[lastfm.EntityType]:
        """Convert callback Entity to lastfm.EntityType."""
        import lastfm as lfm

        if self.entity is None:
            return None
        mapping = {
            Entity.ARTIST: lfm.EntityType.ARTIST,
            Entity.ALBUM: lfm.EntityType.ALBUM,
            Entity.TRACK: lfm.EntityType.TRACK,
        }
        return mapping.get(self.entity)

    def to_lastfm_period(self) -> Optional[lastfm.Period]:
        """Convert callback Period to lastfm.Period."""
        import lastfm as lfm

        if self.period is None:
            return None
        mapping = {
            Period.WEEK: lfm.Period.WEEK,
            Period.MONTH_1: lfm.Period.ONE_MONTH,
            Period.MONTH_3: lfm.Period.THREE_MONTHS,
            Period.MONTH_6: lfm.Period.SIX_MONTHS,
            Period.YEAR: lfm.Period.YEAR,
            Period.OVERALL: lfm.Period.OVERALL,
        }
        return mapping.get(self.period)


def entity_from_lastfm(entity_type: lastfm.EntityType) -> Entity:
    """Convert lastfm.EntityType to callback Entity."""
    import lastfm as lfm

    mapping = {
        lfm.EntityType.ARTIST: Entity.ARTIST,
        lfm.EntityType.ALBUM: Entity.ALBUM,
        lfm.EntityType.TRACK: Entity.TRACK,
    }
    return mapping[entity_type]


def period_from_lastfm(period: lastfm.Period) -> Period:
    """Convert lastfm.Period to callback Period."""
    import lastfm as lfm

    mapping = {
        lfm.Period.WEEK: Period.WEEK,
        lfm.Period.ONE_MONTH: Period.MONTH_1,
        lfm.Period.THREE_MONTHS: Period.MONTH_3,
        lfm.Period.SIX_MONTHS: Period.MONTH_6,
        lfm.Period.YEAR: Period.YEAR,
        lfm.Period.OVERALL: Period.OVERALL,
    }
    return mapping[period]
