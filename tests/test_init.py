"""Tests for setting up the integration and its entities."""

from __future__ import annotations

from datetime import timedelta
from typing import TYPE_CHECKING, Any

from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import (
    CONF_LATITUDE,
    CONF_LONGITUDE,
    CONF_RADIUS,
    STATE_UNAVAILABLE,
    STATE_UNKNOWN,
)
from homeassistant.core import Event, EventStateChangedData, callback
from homeassistant.helpers.event import async_track_state_change_event
from pytest_homeassistant_custom_component.common import (
    MockConfigEntry,
    async_fire_time_changed,
)
from pytest_homeassistant_custom_component.test_util.aiohttp import (
    AiohttpClientMockResponse,
)

from custom_components.officiele_bekendmakingen.api import SRU_URL
from custom_components.officiele_bekendmakingen.const import CONF_TYPES, DOMAIN
from custom_components.officiele_bekendmakingen.coordinator import storage_key
from custom_components.officiele_bekendmakingen.diagnostics import (
    async_get_config_entry_diagnostics,
)

from .helpers import (
    BUILDING,
    CAFE,
    FAR_AWAY,
    HOME_LATITUDE,
    STREET,
    calls_to,
    mock_services,
    search_response,
)

if TYPE_CHECKING:
    from freezegun.api import FrozenDateTimeFactory
    from homeassistant.core import HomeAssistant, State
    from pytest_homeassistant_custom_component.test_util.aiohttp import (
        AiohttpClientMocker,
    )
    from yarl import URL

SENSOR = "sensor.bekendmakingen_thuis_notices"
EVENT = "event.bekendmakingen_thuis_new_notice"
CAFE_LOCATION = "geo_location.officiele_bekendmakingen_gmb_2026_499790"
BUILDING_LOCATION = "geo_location.officiele_bekendmakingen_gmb_2026_542305"


async def _setup(hass: HomeAssistant, entry: MockConfigEntry) -> None:
    if hass.config_entries.async_get_entry(entry.entry_id) is None:
        entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()


async def _next_update(hass: HomeAssistant, freezer: FrozenDateTimeFactory) -> None:
    freezer.tick(timedelta(hours=1))
    async_fire_time_changed(hass)
    await hass.async_block_till_done(wait_background_tasks=True)


def _get(hass: HomeAssistant, entity_id: str) -> State:
    state = hass.states.get(entity_id)
    assert state is not None, f"{entity_id} does not exist"
    return state


async def test_sensor(
    hass: HomeAssistant,
    mock_api: AiohttpClientMocker,
    config_entry: MockConfigEntry,
) -> None:
    """The sensor counts the notices in the radius and lists them, newest first."""
    await _setup(hass, config_entry)

    assert config_entry.state is ConfigEntryState.LOADED
    sensor = _get(hass, SENSOR)
    assert sensor.state == "3"
    notices = sensor.attributes["notices"]
    assert [notice["identifier"] for notice in notices] == [BUILDING, STREET, CAFE]
    assert notices[2] == {
        "identifier": CAFE,
        "title": notices[2]["title"],
        "type": "andere vergunning",
        "authority": "Arnhem",
        "publication": "Gemeenteblad",
        "published": "2026-10-27",
        "url": "https://zoek.officielebekendmakingen.nl/gmb-2026-499790.html",
        "location": "Oude Stationsstraat 16, Arnhem",
        "distance": 59,
    }

    # The search asks for the municipalities of the entry, 30 days back.
    query = mock_api.mock_calls[0][1].query["query"]
    assert query == 'dt.modified>=2026-10-22 AND (w.ligtInGemeente=="Arnhem")'


async def test_radius_and_types(
    hass: HomeAssistant,
    mock_api: AiohttpClientMocker,  # noqa: ARG001  # pylint: disable=unused-argument
    config_entry: MockConfigEntry,
) -> None:
    """A smaller radius and a choice of types leave notices out."""
    config_entry.add_to_hass(hass)
    hass.config_entries.async_update_entry(
        config_entry,
        data={
            **config_entry.data,
            CONF_RADIUS: 200,
            CONF_TYPES: ["omgevingsvergunning"],
        },
    )
    await _setup(hass, config_entry)

    sensor = _get(hass, SENSOR)
    assert [notice["identifier"] for notice in sensor.attributes["notices"]] == [STREET]


async def test_map(
    hass: HomeAssistant,
    mock_api: AiohttpClientMocker,  # noqa: ARG001  # pylint: disable=unused-argument
    config_entry: MockConfigEntry,
) -> None:
    """Every notice in the radius is on the map, at the place it is about."""
    await _setup(hass, config_entry)

    assert len(hass.states.async_entity_ids("geo_location")) == 3
    cafe = _get(hass, CAFE_LOCATION)
    assert cafe.state == "59"
    assert cafe.attributes["source"] == DOMAIN
    assert round(cafe.attributes["latitude"], 4) == 51.9841
    assert round(cafe.attributes["longitude"], 4) == 5.9041
    assert cafe.attributes["unit_of_measurement"] == "m"
    assert cafe.attributes["type"] == "andere vergunning"
    assert cafe.attributes["location"] == "Oude Stationsstraat 16, Arnhem"
    assert cafe.attributes["friendly_name"].startswith("Gemeente Arnhem")


async def test_new_notice(
    hass: HomeAssistant,
    aioclient_mock: AiohttpClientMocker,
    config_entry: MockConfigEntry,
    freezer: FrozenDateTimeFactory,
) -> None:
    """A notice that appears fires the event and is put on the map."""
    mock_services(aioclient_mock, without=(BUILDING,))
    await _setup(hass, config_entry)

    # The notices that were already there are not news.
    assert _get(hass, EVENT).state == STATE_UNKNOWN
    assert hass.states.get(BUILDING_LOCATION) is None

    aioclient_mock.clear_requests()
    mock_services(aioclient_mock)
    await _next_update(hass, freezer)

    event = _get(hass, EVENT)
    assert event.state != STATE_UNKNOWN
    assert event.attributes["event_type"] == "published"
    assert event.attributes["identifier"] == BUILDING
    assert event.attributes["type"] == "omgevingsvergunning"
    assert event.attributes["distance"] == 390
    assert event.attributes["url"].endswith(f"{BUILDING}.html")
    assert _get(hass, SENSOR).state == "3"
    assert _get(hass, BUILDING_LOCATION).state == "390"

    # The same notices again are not news.
    fired = event.state
    await _next_update(hass, freezer)
    assert _get(hass, EVENT).state == fired


async def test_notice_disappears(
    hass: HomeAssistant,
    mock_api: AiohttpClientMocker,
    config_entry: MockConfigEntry,
    freezer: FrozenDateTimeFactory,
) -> None:
    """A notice that is no longer found is taken off the map."""
    await _setup(hass, config_entry)
    assert hass.states.get(CAFE_LOCATION) is not None

    mock_api.clear_requests()
    mock_services(mock_api, without=(CAFE,))
    await _next_update(hass, freezer)

    assert hass.states.get(CAFE_LOCATION) is None
    assert _get(hass, SENSOR).state == "2"
    assert _get(hass, EVENT).state == STATE_UNKNOWN


async def test_new_notice_during_restart(
    hass: HomeAssistant,
    aioclient_mock: AiohttpClientMocker,
    config_entry: MockConfigEntry,
    hass_storage: dict[str, Any],
) -> None:
    """A notice published while Home Assistant was off fires the event."""
    hass_storage[storage_key(config_entry.entry_id)] = {
        "version": 1,
        "minor_version": 1,
        "key": storage_key(config_entry.entry_id),
        "data": {
            "search": [HOME_LATITUDE, 5.905, 500, 30, [], ["Arnhem"]],
            "seen": [CAFE, STREET],
        },
    }
    mock_services(aioclient_mock)
    changes: list[tuple[str | None, str]] = []

    @callback
    def _record(event: Event[EventStateChangedData]) -> None:
        old, new = event.data["old_state"], event.data["new_state"]
        assert new is not None
        changes.append((old.state if old else None, new.state))

    async_track_state_change_event(hass, EVENT, _record)
    await _setup(hass, config_entry)

    assert _get(hass, EVENT).attributes["identifier"] == BUILDING
    # The event comes after the entity has a state: triggers ignore an event
    # that comes straight from unavailable or from nothing.
    assert [old for old, _ in changes] == [None, STATE_UNKNOWN]


async def test_changed_search_is_not_news(
    hass: HomeAssistant,
    aioclient_mock: AiohttpClientMocker,
    config_entry: MockConfigEntry,
    hass_storage: dict[str, Any],
) -> None:
    """Notices that come in by a larger radius do not fire the event."""
    hass_storage[storage_key(config_entry.entry_id)] = {
        "version": 1,
        "minor_version": 1,
        "key": storage_key(config_entry.entry_id),
        "data": {
            "search": [HOME_LATITUDE, 5.905, 200, 30, [], ["Arnhem"]],
            "seen": [CAFE, STREET],
        },
    }
    mock_services(aioclient_mock)
    await _setup(hass, config_entry)

    assert _get(hass, SENSOR).state == "3"
    assert _get(hass, EVENT).state == STATE_UNKNOWN


async def test_seen_notices_are_stored(
    hass: HomeAssistant,
    mock_api: AiohttpClientMocker,  # noqa: ARG001  # pylint: disable=unused-argument
    config_entry: MockConfigEntry,
    hass_storage: dict[str, Any],
    freezer: FrozenDateTimeFactory,
) -> None:
    """The notices are remembered, and forgotten when the entry is removed."""
    await _setup(hass, config_entry)
    freezer.tick(timedelta(seconds=30))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    key = storage_key(config_entry.entry_id)
    assert hass_storage[key]["data"]["seen"] == sorted([BUILDING, CAFE, STREET])
    assert FAR_AWAY not in hass_storage[key]["data"]["seen"]

    await hass.config_entries.async_remove(config_entry.entry_id)
    await hass.async_block_till_done()
    assert key not in hass_storage


async def test_pages(
    hass: HomeAssistant,
    aioclient_mock: AiohttpClientMocker,
    config_entry: MockConfigEntry,
) -> None:
    """All pages of the search results are read."""
    pages = iter(
        [
            search_response(without=(CAFE,)).replace(
                "</sru:records>",
                "</sru:records><sru:nextRecordPosition>501</sru:nextRecordPosition>",
            ),
            search_response(without=(BUILDING, STREET, FAR_AWAY)),
        ]
    )

    async def _answer(method: str, url: URL, _data: Any) -> AiohttpClientMockResponse:
        return AiohttpClientMockResponse(method, url, text=next(pages))

    aioclient_mock.get(SRU_URL, side_effect=_answer)
    await _setup(hass, config_entry)

    assert _get(hass, SENSOR).state == "3"
    assert [call[1].query["startRecord"] for call in aioclient_mock.mock_calls] == [
        "1",
        "501",
    ]


async def test_unreachable_retries_setup(
    hass: HomeAssistant,
    aioclient_mock: AiohttpClientMocker,
    config_entry: MockConfigEntry,
) -> None:
    """When the search cannot be reached, the setup is retried later."""
    aioclient_mock.get(SRU_URL, exc=TimeoutError())
    await _setup(hass, config_entry)

    assert config_entry.state is ConfigEntryState.SETUP_RETRY


async def test_failed_update(
    hass: HomeAssistant,
    mock_api: AiohttpClientMocker,
    config_entry: MockConfigEntry,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Entities are unavailable while the search fails, the map keeps its notices."""
    await _setup(hass, config_entry)

    mock_api.clear_requests()
    mock_api.get(SRU_URL, status=503)
    await _next_update(hass, freezer)
    assert _get(hass, SENSOR).state == STATE_UNAVAILABLE
    assert _get(hass, EVENT).state == STATE_UNAVAILABLE
    assert hass.states.get(CAFE_LOCATION) is not None

    mock_api.clear_requests()
    mock_services(mock_api)
    await _next_update(hass, freezer)
    assert _get(hass, SENSOR).state == "3"
    assert _get(hass, EVENT).state == STATE_UNKNOWN
    assert calls_to(mock_api, SRU_URL) == 1


async def test_unload(
    hass: HomeAssistant,
    mock_api: AiohttpClientMocker,  # noqa: ARG001  # pylint: disable=unused-argument
    config_entry: MockConfigEntry,
) -> None:
    """Unloading the entry makes its entities unavailable and clears the map."""
    await _setup(hass, config_entry)

    assert await hass.config_entries.async_unload(config_entry.entry_id)
    await hass.async_block_till_done()

    assert config_entry.state is ConfigEntryState.NOT_LOADED
    assert _get(hass, SENSOR).state == STATE_UNAVAILABLE
    assert not hass.states.async_entity_ids("geo_location")


async def test_diagnostics(
    hass: HomeAssistant,
    mock_api: AiohttpClientMocker,  # noqa: ARG001  # pylint: disable=unused-argument
    config_entry: MockConfigEntry,
) -> None:
    """Diagnostics count the notices, without the location."""
    await _setup(hass, config_entry)

    diagnostics = await async_get_config_entry_diagnostics(hass, config_entry)

    assert diagnostics["entry"][CONF_LATITUDE] == "**REDACTED**"
    assert diagnostics["entry"][CONF_LONGITUDE] == "**REDACTED**"
    assert "Arnhem" not in str(diagnostics)
    assert diagnostics["notices"] == 3
    assert diagnostics["notice_types"] == {
        "omgevingsvergunning": 2,
        "andere vergunning": 1,
    }
