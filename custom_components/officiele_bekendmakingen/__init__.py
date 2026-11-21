"""The Officiële Bekendmakingen integration: official notices near a location."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from homeassistant.const import Platform
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.storage import Store

from .api import BekendmakingenClient
from .coordinator import (
    BekendmakingenConfigEntry,
    BekendmakingenCoordinator,
    storage_key,
)

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant

PLATFORMS: list[Platform] = [Platform.EVENT, Platform.GEO_LOCATION, Platform.SENSOR]


async def async_setup_entry(
    hass: HomeAssistant, entry: BekendmakingenConfigEntry
) -> bool:
    """Set up a location from a config entry."""
    client = BekendmakingenClient(async_get_clientsession(hass))
    coordinator = BekendmakingenCoordinator(hass, entry, client)
    await coordinator.async_config_entry_first_refresh()
    entry.runtime_data = coordinator
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(
    hass: HomeAssistant, entry: BekendmakingenConfigEntry
) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)


async def async_remove_entry(
    hass: HomeAssistant, entry: BekendmakingenConfigEntry
) -> None:
    """Forget the notices that were seen for a removed entry."""
    store: Store[dict[str, Any]] = Store(hass, 1, storage_key(entry.entry_id))
    await store.async_remove()
