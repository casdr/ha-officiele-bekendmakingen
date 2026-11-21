"""Tests for the config flow."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from homeassistant.config_entries import SOURCE_USER
from homeassistant.const import (
    CONF_LATITUDE,
    CONF_LOCATION,
    CONF_LONGITUDE,
    CONF_NAME,
    CONF_RADIUS,
)
from homeassistant.data_entry_flow import FlowResultType

from custom_components.officiele_bekendmakingen.api import PDOK_REVERSE_URL
from custom_components.officiele_bekendmakingen.const import (
    CONF_DAYS,
    CONF_MUNICIPALITIES,
    CONF_TYPES,
    DOMAIN,
)

from .helpers import HOME_LATITUDE, HOME_LONGITUDE, load_text

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant
    from pytest_homeassistant_custom_component.common import MockConfigEntry
    from pytest_homeassistant_custom_component.test_util.aiohttp import (
        AiohttpClientMocker,
    )

USER_INPUT: dict[str, Any] = {
    CONF_NAME: "Bekendmakingen thuis",
    CONF_LOCATION: {
        CONF_LATITUDE: HOME_LATITUDE,
        CONF_LONGITUDE: HOME_LONGITUDE,
        CONF_RADIUS: 750,
    },
    CONF_TYPES: ["omgevingsvergunning"],
    CONF_DAYS: 14,
}


def _suggested(result: Any) -> dict[str, Any]:
    """Return the suggested values of a form."""
    return {
        str(key): key.description["suggested_value"]
        for key in result["data_schema"].schema
        if key.description
    }


async def test_user_flow(hass: HomeAssistant, mock_api: AiohttpClientMocker) -> None:
    """The form starts at home, the entry gets the municipalities around it."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"
    suggested = _suggested(result)
    assert suggested[CONF_NAME] == "Bekendmakingen test home"
    assert suggested[CONF_LOCATION] == {
        CONF_LATITUDE: HOME_LATITUDE,
        CONF_LONGITUDE: HOME_LONGITUDE,
        CONF_RADIUS: 500,
    }
    assert suggested[CONF_DAYS] == 30

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], USER_INPUT
    )
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "Bekendmakingen thuis"
    assert result["data"] == {
        CONF_LATITUDE: HOME_LATITUDE,
        CONF_LONGITUDE: HOME_LONGITUDE,
        CONF_RADIUS: 750,
        CONF_TYPES: ["omgevingsvergunning"],
        CONF_DAYS: 14,
        CONF_MUNICIPALITIES: ["Arnhem"],
    }
    lookup = next(
        call
        for call in mock_api.mock_calls
        if str(call[1]).startswith(PDOK_REVERSE_URL)
    )
    assert lookup[1].query["distance"] == "1000"


async def test_all_types(
    hass: HomeAssistant,
    mock_api: AiohttpClientMocker,  # noqa: ARG001  # pylint: disable=unused-argument
) -> None:
    """Without a choice of types, all notices are followed."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    user_input = {key: value for key, value in USER_INPUT.items() if key != CONF_TYPES}
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input
    )
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"][CONF_TYPES] == []


async def test_lookup_fails(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """A failed municipality lookup shows an error, and a retry works."""
    aioclient_mock.get(PDOK_REVERSE_URL, status=503)
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], USER_INPUT
    )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "cannot_connect"}
    # The form keeps what was filled in.
    assert _suggested(result)[CONF_DAYS] == 14

    aioclient_mock.clear_requests()
    aioclient_mock.get(PDOK_REVERSE_URL, text=load_text("municipalities.json"))
    aioclient_mock.get(
        "https://repository.overheid.nl/sru", text=load_text("search.xml")
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], USER_INPUT
    )
    await hass.async_block_till_done()
    assert result["type"] is FlowResultType.CREATE_ENTRY


async def test_outside_netherlands(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """A location without a Dutch municipality nearby is refused."""
    aioclient_mock.get(PDOK_REVERSE_URL, json={"response": {"docs": []}})
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], USER_INPUT
    )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {CONF_LOCATION: "outside_netherlands"}


async def test_reconfigure(
    hass: HomeAssistant,
    mock_api: AiohttpClientMocker,  # noqa: ARG001  # pylint: disable=unused-argument
    config_entry: MockConfigEntry,
) -> None:
    """Reconfiguring starts with the current settings and replaces them."""
    config_entry.add_to_hass(hass)
    result = await config_entry.start_reconfigure_flow(hass)
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reconfigure"
    suggested = _suggested(result)
    assert suggested[CONF_NAME] == "Bekendmakingen thuis"
    assert suggested[CONF_LOCATION][CONF_RADIUS] == 500

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {**USER_INPUT, CONF_NAME: "Bekendmakingen werk"}
    )
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reconfigure_successful"
    assert config_entry.title == "Bekendmakingen werk"
    assert config_entry.data[CONF_RADIUS] == 750
    assert config_entry.data[CONF_DAYS] == 14
    assert config_entry.data[CONF_TYPES] == ["omgevingsvergunning"]
