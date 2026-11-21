"""Shared fixtures for the Officiële Bekendmakingen tests."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from homeassistant.const import CONF_LATITUDE, CONF_LONGITUDE, CONF_RADIUS
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.officiele_bekendmakingen.const import (
    CONF_DAYS,
    CONF_MUNICIPALITIES,
    CONF_TYPES,
    DOMAIN,
)

from .helpers import HOME_LATITUDE, HOME_LONGITUDE, NOW, mock_services

if TYPE_CHECKING:
    from freezegun.api import FrozenDateTimeFactory
    from homeassistant.core import HomeAssistant
    from pytest_homeassistant_custom_component.test_util.aiohttp import (
        AiohttpClientMocker,
    )


@pytest.fixture(autouse=True)
def auto_enable_custom_integrations(  # pylint: disable=unused-argument
    enable_custom_integrations: None,
) -> None:
    """Load the integration from custom_components."""


@pytest.fixture(autouse=True)
def home(hass: HomeAssistant, freezer: FrozenDateTimeFactory) -> None:
    """Put Home Assistant in Arnhem, at the moment of the fixtures."""
    freezer.move_to(NOW)
    hass.config.latitude = HOME_LATITUDE
    hass.config.longitude = HOME_LONGITUDE


@pytest.fixture(name="mock_api")
def mock_api_fixture(aioclient_mock: AiohttpClientMocker) -> AiohttpClientMocker:
    """Answer the notice search and the municipality lookup with the fixtures."""
    mock_services(aioclient_mock)
    return aioclient_mock


@pytest.fixture(name="config_entry")
def config_entry_fixture() -> MockConfigEntry:
    """Return an entry that follows all notices within 500 m."""
    return MockConfigEntry(
        domain=DOMAIN,
        title="Bekendmakingen thuis",
        data={
            CONF_LATITUDE: HOME_LATITUDE,
            CONF_LONGITUDE: HOME_LONGITUDE,
            CONF_RADIUS: 500,
            CONF_TYPES: [],
            CONF_DAYS: 30,
            CONF_MUNICIPALITIES: ["Arnhem"],
        },
    )
