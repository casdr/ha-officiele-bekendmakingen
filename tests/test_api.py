"""Tests for the client and the parser of the search results."""

from __future__ import annotations

from datetime import date
from typing import TYPE_CHECKING

import pytest
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from custom_components.officiele_bekendmakingen.api import (
    PDOK_REVERSE_URL,
    SRU_URL,
    BekendmakingenClient,
    BekendmakingenConnectionError,
    BekendmakingenResponseError,
    build_query,
    parse_page,
)

from .helpers import (
    BUILDING,
    CAFE,
    FAR_AWAY,
    HOME_LATITUDE,
    HOME_LONGITUDE,
    STREET,
    load_text,
)

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant
    from pytest_homeassistant_custom_component.test_util.aiohttp import (
        AiohttpClientMocker,
    )

DIAGNOSTIC = (
    '<searchRetrieveResponse xmlns="http://docs.oasis-open.org/ns/search-ws/sruResponse"'
    ' xmlns:ns3="http://docs.oasis-open.org/ns/search-ws/diagnostic"><diagnostics>'
    "<ns3:diagnostic><ns3:message>maximumRecords is 1000</ns3:message>"
    "</ns3:diagnostic></diagnostics></searchRetrieveResponse>"
)


def test_parse_page() -> None:
    """Every notice gets its details and the distance to the position."""
    page = parse_page(load_text("search.xml"), HOME_LATITUDE, HOME_LONGITUDE)

    assert page.next_position is None
    notices = {notice.identifier: notice for notice in page.notices}
    assert set(notices) == {CAFE, STREET, BUILDING, FAR_AWAY}

    cafe = notices[CAFE]
    assert cafe.notice_type == "andere vergunning"
    assert cafe.authority == "Arnhem"
    assert cafe.publication == "Gemeenteblad"
    assert cafe.published == date(2026, 10, 27)
    assert cafe.location == "Oude Stationsstraat 16, Arnhem"
    assert cafe.url == "https://zoek.officielebekendmakingen.nl/gmb-2026-499790.html"
    assert cafe.distance == pytest.approx(59, abs=1)
    assert (cafe.latitude, cafe.longitude) == pytest.approx((51.984068, 5.9041452))

    # A street is several lines: the nearest one counts.
    street = notices[STREET]
    assert street.authority == "Gelderland"
    assert street.publication == "Provinciaal blad"
    assert street.location == "Nieuwe Plein, Arnhem"
    assert street.distance == pytest.approx(147, abs=1)

    assert notices[BUILDING].activities
    assert notices[BUILDING].location is None
    assert notices[FAR_AWAY].distance == pytest.approx(5221, abs=5)


def test_parse_page_with_next_position() -> None:
    """A response with more results tells where the next page starts."""
    content = load_text("search.xml").replace(
        "</sru:records>",
        "</sru:records><sru:nextRecordPosition>501</sru:nextRecordPosition>",
    )

    assert parse_page(content, HOME_LATITUDE, HOME_LONGITUDE).next_position == 501


@pytest.mark.parametrize(
    ("content", "error"),
    [
        (DIAGNOSTIC, "maximumRecords is 1000"),
        ("<html>Service unavailable", "not XML"),
        ("<other/>", "no record count"),
    ],
)
def test_parse_page_errors(content: str, error: str) -> None:
    """A failed search or another kind of answer is an error."""
    with pytest.raises(BekendmakingenResponseError, match=error):
        parse_page(content, HOME_LATITUDE, HOME_LONGITUDE)


def test_build_query() -> None:
    """The query asks for notices in the municipalities since a date."""
    assert build_query(["Arnhem", "'s-Gravenhage"], date(2026, 10, 22)) == (
        'dt.modified>=2026-10-22 AND (w.ligtInGemeente=="Arnhem"'
        ' OR w.ligtInGemeente=="\'s-Gravenhage")'
    )
    assert '"a\\"b"' in build_query(['a"b'], date(2026, 10, 22))


async def test_get_municipalities(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """The lookup sends a rounded position and returns the names."""
    aioclient_mock.get(
        PDOK_REVERSE_URL,
        json={
            "response": {
                "docs": [
                    {"gemeentenaam": "Rheden"},
                    {"gemeentenaam": "Arnhem"},
                ]
            }
        },
    )
    client = BekendmakingenClient(async_get_clientsession(hass))

    names = await client.async_get_municipalities(52.37403659, 4.88969054, 500)

    assert names == ["Arnhem", "Rheden"]
    params = aioclient_mock.mock_calls[0][1].query
    assert params["lat"] == "52.374"
    assert params["lon"] == "4.890"
    assert params["distance"] == "750"


async def test_client_errors(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """An HTTP error, a timeout and an unexpected answer are client errors."""
    client = BekendmakingenClient(async_get_clientsession(hass))

    aioclient_mock.get(SRU_URL, status=503)
    with pytest.raises(BekendmakingenResponseError, match="HTTP 503"):
        await client.async_search("query")

    aioclient_mock.clear_requests()
    aioclient_mock.get(SRU_URL, exc=TimeoutError())
    with pytest.raises(BekendmakingenConnectionError):
        await client.async_search("query")

    aioclient_mock.get(PDOK_REVERSE_URL, json={"error": "bad request"})
    with pytest.raises(BekendmakingenResponseError, match="unexpected answer"):
        await client.async_get_municipalities(51.98, 5.96, 500)
