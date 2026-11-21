"""Data update coordinator: the notices near the configured location."""

from __future__ import annotations

import logging
from datetime import timedelta
from typing import TYPE_CHECKING, Any, Final

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_LATITUDE, CONF_LONGITUDE, CONF_RADIUS
from homeassistant.helpers.storage import Store
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.util import dt as dt_util

from .api import (
    PAGE_SIZE,
    BekendmakingenClient,
    BekendmakingenError,
    Notice,
    build_query,
    parse_page,
)
from .const import (
    CONF_DAYS,
    CONF_MUNICIPALITIES,
    CONF_TYPES,
    DOMAIN,
    UPDATE_INTERVAL,
)

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant

_LOGGER = logging.getLogger(__name__)

# Stop paging when the service keeps returning pages.
_MAX_PAGES: Final = 20
_STORAGE_VERSION: Final = 1
_SAVE_DELAY: Final = 10

type BekendmakingenConfigEntry = ConfigEntry[BekendmakingenCoordinator]


def storage_key(entry_id: str) -> str:
    """Return the key of the file that remembers the notices of an entry."""
    return f"{DOMAIN}.{entry_id}"


class BekendmakingenCoordinator(DataUpdateCoordinator[list[Notice]]):
    """The notices within the radius, newest first.

    The notices seen before are remembered across restarts, so that only notices
    that are really new are announced.
    """

    config_entry: BekendmakingenConfigEntry

    def __init__(
        self,
        hass: HomeAssistant,
        entry: BekendmakingenConfigEntry,
        client: BekendmakingenClient,
    ) -> None:
        """Initialize the coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            config_entry=entry,
            name=f"{DOMAIN} {entry.title}",
            update_interval=UPDATE_INTERVAL,
        )
        self._client = client
        self._latitude: float = entry.data[CONF_LATITUDE]
        self._longitude: float = entry.data[CONF_LONGITUDE]
        self._radius: float = entry.data[CONF_RADIUS]
        self._days: int = entry.data[CONF_DAYS]
        self._types: frozenset[str] = frozenset(entry.data.get(CONF_TYPES, ()))
        self._municipalities: list[str] = entry.data[CONF_MUNICIPALITIES]
        # Changing what is searched for brings in old notices, which are not news.
        self._search = [
            self._latitude,
            self._longitude,
            self._radius,
            self._days,
            sorted(self._types),
            self._municipalities,
        ]
        self._store: Store[dict[str, Any]] = Store(
            hass, _STORAGE_VERSION, storage_key(entry.entry_id)
        )
        self._seen: set[str] | None = None
        self.new_notices: list[Notice] = []
        """The notices that appeared in the latest update, oldest first."""

    async def _async_setup(self) -> None:
        stored = await self._store.async_load()
        if stored and stored.get("search") == self._search:
            self._seen = set(stored["seen"])

    async def _async_update_data(self) -> list[Notice]:
        since = dt_util.now().date() - timedelta(days=self._days)
        query = build_query(self._municipalities, since)
        found: dict[str, Notice] = {}
        position = 1
        try:
            for _ in range(_MAX_PAGES):
                content = await self._client.async_search(query, position)
                page = await self.hass.async_add_executor_job(
                    parse_page, content, self._latitude, self._longitude
                )
                for notice in page.notices:
                    found.setdefault(notice.identifier, notice)
                if page.next_position is None:
                    break
                position = page.next_position
            else:
                _LOGGER.warning(
                    "More than %s notices in %s days, the oldest are left out",
                    _MAX_PAGES * PAGE_SIZE,
                    self._days,
                )
        except BekendmakingenError as err:
            raise UpdateFailed(
                translation_domain=DOMAIN,
                translation_key="update_failed",
                translation_placeholders={"error": str(err)},
            ) from err

        notices = sorted(
            (
                notice
                for notice in found.values()
                if notice.distance <= self._radius
                and (not self._types or notice.notice_type in self._types)
            ),
            key=lambda notice: (-notice.published.toordinal(), notice.distance),
        )
        identifiers = {notice.identifier for notice in notices}
        if self._seen is None:
            # The first search: everything is already published, nothing is news.
            self.new_notices = []
        else:
            self.new_notices = [
                notice
                for notice in reversed(notices)
                if notice.identifier not in self._seen
            ]
        if identifiers != self._seen:
            self._seen = identifiers
            self._store.async_delay_save(self._data_to_save, _SAVE_DELAY)
        return notices

    def _data_to_save(self) -> dict[str, Any]:
        return {"search": self._search, "seen": sorted(self._seen or ())}
