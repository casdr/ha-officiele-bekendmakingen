"""Every notice near the location as an entity on the map."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from homeassistant.components.geo_location import ENTITY_ID_FORMAT, GeolocationEvent
from homeassistant.const import UnitOfLength
from homeassistant.core import callback
from homeassistant.helpers.entity import async_generate_entity_id

from .const import ATTRIBUTION, DOMAIN

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant
    from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

    from .api import Notice
    from .coordinator import BekendmakingenConfigEntry

PARALLEL_UPDATES = 0


async def async_setup_entry(
    hass: HomeAssistant,
    entry: BekendmakingenConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Add an entity for every notice, and remove it when the notice is gone."""
    coordinator = entry.runtime_data
    entities: dict[str, NoticeLocation] = {}

    @callback
    def _async_sync() -> None:
        if not coordinator.last_update_success:
            return
        notices = {notice.identifier: notice for notice in coordinator.data}
        for identifier in entities.keys() - notices.keys():
            hass.async_create_task(entities.pop(identifier).async_remove())
        added = {
            identifier: NoticeLocation(hass, notice)
            for identifier, notice in notices.items()
            if identifier not in entities
        }
        entities.update(added)
        async_add_entities(added.values())

    _async_sync()
    entry.async_on_unload(coordinator.async_add_listener(_async_sync))


class NoticeLocation(GeolocationEvent):
    """A notice at the place it is about."""

    _attr_should_poll = False
    _attr_attribution = ATTRIBUTION
    _attr_source = DOMAIN
    _attr_unit_of_measurement = UnitOfLength.METERS

    def __init__(self, hass: HomeAssistant, notice: Notice) -> None:
        """Initialize the entity."""
        self.entity_id = async_generate_entity_id(
            ENTITY_ID_FORMAT, f"{DOMAIN}_{notice.identifier}", hass=hass
        )
        self._notice = notice
        self._attr_name = notice.title
        self._attr_distance = round(notice.distance)
        self._attr_latitude = notice.latitude
        self._attr_longitude = notice.longitude

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return the details of the notice."""
        return {
            key: value
            for key, value in self._notice.as_dict().items()
            if key not in {"title", "latitude", "longitude", "distance"}
        }
