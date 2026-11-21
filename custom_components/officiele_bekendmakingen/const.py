"""Constants for the Officiële Bekendmakingen integration."""

from __future__ import annotations

from datetime import timedelta
from typing import Final

DOMAIN: Final = "officiele_bekendmakingen"

MANUFACTURER: Final = "KOOP"
ATTRIBUTION: Final = "Data provided by officielebekendmakingen.nl"
CONFIGURATION_URL: Final = "https://www.officielebekendmakingen.nl"

CONF_TYPES: Final = "types"
CONF_DAYS: Final = "days"
CONF_MUNICIPALITIES: Final = "municipalities"

DEFAULT_RADIUS: Final = 500
DEFAULT_DAYS: Final = 30
MAX_DAYS: Final = 90

# Notices are published throughout the working day.
UPDATE_INTERVAL: Final = timedelta(hours=1)

EVENT_PUBLISHED: Final = "published"

# The notice types (OVERHEIDop.Rubriek) that come with a location, most common first.
NOTICE_TYPES: Final = (
    "omgevingsvergunning",
    "andere vergunning",
    "verkeersbesluit of -mededeling",
    "evenementenvergunning",
    "exploitatievergunning",
    "andere beschikking",
    "omgevingsmelding",
    "andere melding",
    "evenementmelding",
    "ander besluit van algemene strekking",
    "ruimtelijk plan of omgevingsdocument",
    "participatie",
    "overige overheidsinformatie",
)
