"""Event entity that fires for every new notice near the location."""

from __future__ import annotations

from typing import TYPE_CHECKING

from homeassistant.components.event import EventEntity
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.start import async_at_started

from .const import EVENT_PUBLISHED
from .entity import BekendmakingenEntity

if TYPE_CHECKING:
    from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

    from .coordinator import BekendmakingenConfigEntry

PARALLEL_UPDATES = 0


async def async_setup_entry(
    hass: HomeAssistant,  # noqa: ARG001  # pylint: disable=unused-argument
    entry: BekendmakingenConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the event entity of a config entry."""
    async_add_entities([NoticeEvent(entry.runtime_data, entry, "notice")])


class NoticeEvent(BekendmakingenEntity, EventEntity):
    """Fires once for every notice that was not there in the previous search."""

    _attr_event_types = [EVENT_PUBLISHED]  # noqa: RUF012

    async def async_added_to_hass(self) -> None:
        """Announce the notices that were published while Home Assistant was off.

        Not right away: triggers ignore an event that comes straight after the
        entity was unavailable, and during startup automations may not listen yet.
        """
        await super().async_added_to_hass()

        @callback
        def _async_announce_soon(hass: HomeAssistant) -> None:
            # After the state that is written when the entity is added.
            hass.loop.call_soon(self._async_announce_missed)

        self.async_on_remove(async_at_started(self.hass, _async_announce_soon))

    @callback
    def _async_announce_missed(self) -> None:
        if self.hass.states.get(self.entity_id) is not None:
            self._async_announce()

    @callback
    def _handle_coordinator_update(self) -> None:
        self._async_announce()
        if not self.coordinator.new_notices:
            # Availability may have changed.
            self.async_write_ha_state()

    @callback
    def _async_announce(self) -> None:
        for notice in self.coordinator.new_notices:
            self._trigger_event(EVENT_PUBLISHED, notice.as_dict())
            self.async_write_ha_state()
