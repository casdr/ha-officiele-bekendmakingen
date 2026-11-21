"""Helpers for the Officiële Bekendmakingen tests."""

from __future__ import annotations

import re
from datetime import UTC, datetime
from pathlib import Path
from typing import TYPE_CHECKING

from custom_components.officiele_bekendmakingen.api import PDOK_REVERSE_URL, SRU_URL

if TYPE_CHECKING:
    from pytest_homeassistant_custom_component.test_util.aiohttp import (
        AiohttpClientMocker,
    )

FIXTURES = Path(__file__).parent / "fixtures"

# Next to Arnhem Centraal. The search fixture has notices at 59 m (a café permit),
# 147 m (a province permit for a street), 390 m (a building permit) and 5.2 km.
HOME_LATITUDE = 51.984
HOME_LONGITUDE = 5.905

NOW = datetime(2026, 11, 21, 22, 27, tzinfo=UTC)

CAFE = "gmb-2026-499790"
STREET = "prb-2026-18709"
BUILDING = "gmb-2026-542305"
FAR_AWAY = "gmb-2026-506859"

_RECORD = re.compile(r"<sru:record>.*?</sru:record>", re.DOTALL)


def load_text(name: str) -> str:
    """Return a text fixture."""
    return (FIXTURES / name).read_text(encoding="utf-8")


def search_response(*, without: tuple[str, ...] = ()) -> str:
    """Return the search fixture, optionally without some notices."""

    def _keep(match: re.Match[str]) -> str:
        record = match.group(0)
        return (
            "" if any(f">{identifier}<" in record for identifier in without) else record
        )

    return _RECORD.sub(_keep, load_text("search.xml"))


def mock_services(
    aioclient_mock: AiohttpClientMocker, *, without: tuple[str, ...] = ()
) -> None:
    """Answer the notice search and the municipality lookup with the fixtures."""
    aioclient_mock.get(SRU_URL, text=search_response(without=without))
    aioclient_mock.get(PDOK_REVERSE_URL, text=load_text("municipalities.json"))


def calls_to(aioclient_mock: AiohttpClientMocker, url: str) -> int:
    """Return how often a URL was requested, ignoring its query."""
    return sum(1 for call in aioclient_mock.mock_calls if str(call[1]).startswith(url))
