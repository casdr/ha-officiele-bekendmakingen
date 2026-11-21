"""Clients for the official notices of the Dutch government.

Notices come from the SRU search service of repository.overheid.nl. Its radius search
fails with a server error, so notices are searched by municipality and filtered by
distance here. The municipalities around a position come from the PDOK geocoder.
"""

from __future__ import annotations

import dataclasses
import json
from datetime import date
from http import HTTPStatus
from typing import TYPE_CHECKING, Any, Final

# The XML comes from the government over HTTPS, and expat limits entity expansion.
from xml.etree import ElementTree as ET

import aiohttp

from .geometry import Area, parse_area

if TYPE_CHECKING:
    from collections.abc import Iterable
    from xml.etree.ElementTree import Element

SRU_URL: Final = "https://repository.overheid.nl/sru"
PDOK_REVERSE_URL: Final = "https://api.pdok.nl/bzk/locatieserver/search/v3_1/reverse"

# The service returns at most 1000 records per request, of about 5 kB each.
PAGE_SIZE: Final = 500
# The geocoder gets a rounded position, so look a bit further than the radius.
MUNICIPALITY_MARGIN: Final = 250

_TIMEOUT: Final = aiohttp.ClientTimeout(total=60)
_NS: Final = {
    "sru": "http://docs.oasis-open.org/ns/search-ws/sruResponse",
    "diag": "http://docs.oasis-open.org/ns/search-ws/diagnostic",
    "gzd": "http://standaarden.overheid.nl/sru",
    "w": "http://standaarden.overheid.nl/wetgeving/",
    "dcterms": "http://purl.org/dc/terms/",
}


class BekendmakingenError(Exception):
    """A request for notices or municipalities failed."""


class BekendmakingenConnectionError(BekendmakingenError):
    """The service could not be reached."""


class BekendmakingenResponseError(BekendmakingenError):
    """The service answered with something this integration does not understand."""


@dataclasses.dataclass(frozen=True, slots=True)
class Notice:
    """An official notice with a location."""

    identifier: str
    title: str
    notice_type: str
    authority: str
    publication: str | None
    published: date
    abstract: str | None
    url: str
    activities: tuple[str, ...]
    location: str | None
    latitude: float
    longitude: float
    distance: float
    """Metres from the configured position to the area of the notice."""

    def as_dict(self) -> dict[str, Any]:
        """Return the notice as state attributes."""
        return {
            "identifier": self.identifier,
            "title": self.title,
            "type": self.notice_type,
            "authority": self.authority,
            "publication": self.publication,
            "published": self.published.isoformat(),
            "abstract": self.abstract,
            "url": self.url,
            "activities": list(self.activities),
            "location": self.location,
            "latitude": self.latitude,
            "longitude": self.longitude,
            "distance": round(self.distance),
        }


@dataclasses.dataclass(frozen=True, slots=True)
class Page:
    """One page of search results."""

    notices: list[Notice]
    next_position: int | None


def build_query(municipalities: Iterable[str], since: date) -> str:
    """Return the CQL query for notices in municipalities, changed since a date."""
    places = " OR ".join(
        f'w.ligtInGemeente=="{_escape(municipality)}"'
        for municipality in municipalities
    )
    return f"dt.modified>={since.isoformat()} AND ({places})"


def _escape(term: str) -> str:
    return term.replace("\\", "\\\\").replace('"', '\\"')


def parse_page(content: str, latitude: float, longitude: float) -> Page:
    """Parse a search response, measuring every notice from a position.

    Notices without an area that can be read are left out.
    """
    try:
        root = ET.fromstring(content)  # noqa: S314
    except ET.ParseError as err:
        msg = "The search response is not XML"
        raise BekendmakingenResponseError(msg) from err
    if (
        message := root.findtext(".//diag:diagnostic/diag:message", None, _NS)
    ) is not None:
        msg = f"The search failed: {message}"
        raise BekendmakingenResponseError(msg)
    if root.find("sru:numberOfRecords", _NS) is None:
        msg = "The search response has no record count"
        raise BekendmakingenResponseError(msg)

    notices = [
        notice
        for record in root.iterfind("sru:records/sru:record", _NS)
        if (notice := _parse_record(record, latitude, longitude)) is not None
    ]
    next_position = root.findtext("sru:nextRecordPosition", None, _NS)
    try:
        return Page(notices, int(next_position) if next_position else None)
    except ValueError as err:
        msg = "The search response has an invalid next record position"
        raise BekendmakingenResponseError(msg) from err


def _text(element: Element, path: str) -> str | None:
    text = element.findtext(path, None, _NS)
    return text.strip() or None if text else None


def _parse_record(record: Element, latitude: float, longitude: float) -> Notice | None:
    identifier = _text(record, ".//dcterms:identifier")
    title = _text(record, ".//dcterms:title")
    published = _text(record, ".//dcterms:date") or _text(record, ".//dcterms:modified")
    if identifier is None or title is None or published is None:
        return None
    try:
        published_on = date.fromisoformat(published[:10])
    except ValueError:
        return None

    nearest: tuple[float, Area, Element] | None = None
    for marker in record.iterfind(".//w:gebiedsmarkering/*", _NS):
        for element in marker.iterfind("w:locatiegebied", _NS):
            area = parse_area(element.text or "")
            if area is None:
                continue
            distance = area.distance_to(latitude, longitude)
            if nearest is None or distance < nearest[0]:
                nearest = (distance, area, marker)
    if nearest is None:
        return None
    distance, area, marker = nearest
    center_latitude, center_longitude = area.center

    return Notice(
        identifier=identifier,
        title=title,
        notice_type=_text(record, ".//dcterms:type") or "",
        authority=_text(record, ".//dcterms:creator") or "",
        publication=_text(record, ".//w:publicatienaam"),
        published=published_on,
        abstract=_text(record, ".//dcterms:abstract"),
        url=_text(record, ".//gzd:preferredUrl")
        or f"https://zoek.officielebekendmakingen.nl/{identifier}.html",
        activities=tuple(
            dict.fromkeys(
                element.text.strip()
                for element in record.iterfind(".//w:activiteit", _NS)
                if element.text and element.text.strip()
            )
        ),
        location=_location(marker),
        latitude=center_latitude,
        longitude=center_longitude,
        distance=distance,
    )


def _location(marker: Element) -> str | None:
    """Return the address of a location marker, or else its label."""
    street = _text(marker, "w:straatnaam")
    if street is None:
        return _text(marker, "w:geometrielabel")
    number = "".join(
        _text(marker, f"w:{part}") or ""
        for part in ("huisnummer", "huisletter", "huisnummertoevoeging")
    )
    address = f"{street} {number}".strip()
    if city := _text(marker, "w:woonplaats"):
        address = f"{address}, {city}"
    return address


class BekendmakingenClient:
    """Client for the notice search and the municipality lookup."""

    def __init__(self, session: aiohttp.ClientSession) -> None:
        """Initialize the client."""
        self._session = session

    async def async_search(self, query: str, start: int = 1) -> str:
        """Return one page of search results as XML, to parse with parse_page."""
        params = {
            "operation": "searchRetrieve",
            "version": "2.0",
            "x-connection": "officielepubs",
            "query": query,
            "startRecord": str(start),
            "maximumRecords": str(PAGE_SIZE),
        }
        return await self._async_get(SRU_URL, params)

    async def async_get_municipalities(
        self, latitude: float, longitude: float, radius: float
    ) -> list[str]:
        """Return the names of the municipalities within a radius of a position."""
        params = {
            # About 100 m precise: enough to find municipalities.
            "lat": f"{latitude:.3f}",
            "lon": f"{longitude:.3f}",
            "type": "gemeente",
            "distance": str(round(radius + MUNICIPALITY_MARGIN)),
            "rows": "50",
            "fl": "gemeentenaam",
        }
        content = await self._async_get(PDOK_REVERSE_URL, params)
        try:
            data = json.loads(content)
            names = {doc["gemeentenaam"] for doc in data["response"]["docs"]}
        except (ValueError, KeyError, TypeError) as err:
            msg = "The municipality lookup returned an unexpected answer"
            raise BekendmakingenResponseError(msg) from err
        return sorted(names)

    async def _async_get(self, url: str, params: dict[str, str]) -> str:
        try:
            async with self._session.get(
                url, params=params, timeout=_TIMEOUT
            ) as response:
                if response.status != HTTPStatus.OK:
                    msg = f"{response.url.host} answered with HTTP {response.status}"
                    raise BekendmakingenResponseError(msg)
                return await response.text()
        except (aiohttp.ClientError, TimeoutError) as err:
            msg = f"Could not reach {url}: {err or type(err).__name__}"
            raise BekendmakingenConnectionError(msg) from err
