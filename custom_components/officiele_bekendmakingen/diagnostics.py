"""Diagnostics, without the location and the notices that give it away."""

from __future__ import annotations

from collections import Counter
from typing import TYPE_CHECKING, Any

from homeassistant.components.diagnostics import async_redact_data
from homeassistant.const import CONF_LATITUDE, CONF_LONGITUDE

from .const import CONF_MUNICIPALITIES

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant

    from .coordinator import BekendmakingenConfigEntry

TO_REDACT = {CONF_LATITUDE, CONF_LONGITUDE, CONF_MUNICIPALITIES}


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant,  # noqa: ARG001  # pylint: disable=unused-argument
    entry: BekendmakingenConfigEntry,
) -> dict[str, Any]:
    """Return diagnostics for a config entry."""
    coordinator = entry.runtime_data
    return {
        "entry": async_redact_data(dict(entry.data), TO_REDACT),
        "last_update_success": coordinator.last_update_success,
        "update_interval": str(coordinator.update_interval),
        "notices": len(coordinator.data),
        "notice_types": dict(Counter(n.notice_type for n in coordinator.data)),
    }
