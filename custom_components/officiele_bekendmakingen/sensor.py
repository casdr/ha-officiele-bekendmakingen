"""Sensor with the number of notices near the location, and the notices themselves."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, Final

from homeassistant.components.sensor import SensorEntity, SensorStateClass

from .entity import BekendmakingenEntity

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant
    from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

    from .coordinator import BekendmakingenConfigEntry

# State attributes are limited in size, and a notice takes about 0.5 kB.
MAX_LISTED: Final = 20

PARALLEL_UPDATES = 0


async def async_setup_entry(
    hass: HomeAssistant,  # noqa: ARG001  # pylint: disable=unused-argument
    entry: BekendmakingenConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the sensor of a config entry."""
    async_add_entities([NoticesSensor(entry.runtime_data, entry, "notices")])


class NoticesSensor(BekendmakingenEntity, SensorEntity):
    """The number of notices near the location, with the newest as attributes."""

    _attr_state_class = SensorStateClass.MEASUREMENT
    _unrecorded_attributes = frozenset({"notices"})

    @property
    def native_value(self) -> int:
        """Return the number of notices."""
        return len(self.coordinator.data)

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return the newest notices."""
        return {
            "notices": [
                {
                    key: value
                    for key, value in notice.as_dict().items()
                    if key not in {"abstract", "activities", "latitude", "longitude"}
                }
                for notice in self.coordinator.data[:MAX_LISTED]
            ]
        }
