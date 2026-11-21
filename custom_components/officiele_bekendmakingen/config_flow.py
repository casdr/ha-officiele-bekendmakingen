"""Config flow for Officiële Bekendmakingen: one entry per location."""

from __future__ import annotations

import logging
from typing import Any

import probatio
from homeassistant.config_entries import (
    SOURCE_RECONFIGURE,
    ConfigFlow,
    ConfigFlowResult,
)
from homeassistant.const import (
    CONF_LATITUDE,
    CONF_LOCATION,
    CONF_LONGITUDE,
    CONF_NAME,
    CONF_RADIUS,
)
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.selector import (
    LocationSelector,
    LocationSelectorConfig,
    NumberSelector,
    NumberSelectorConfig,
    NumberSelectorMode,
    SelectSelector,
    SelectSelectorConfig,
    SelectSelectorMode,
    TextSelector,
)

from .api import BekendmakingenClient, BekendmakingenError
from .const import (
    CONF_DAYS,
    CONF_MUNICIPALITIES,
    CONF_TYPES,
    DEFAULT_DAYS,
    DEFAULT_RADIUS,
    DOMAIN,
    MAX_DAYS,
    NOTICE_TYPES,
)

_LOGGER = logging.getLogger(__name__)

SCHEMA = probatio.Schema(
    {
        probatio.Required(CONF_NAME): TextSelector(),
        probatio.Required(CONF_LOCATION): LocationSelector(
            LocationSelectorConfig(radius=True)
        ),
        probatio.Optional(CONF_TYPES): SelectSelector(
            SelectSelectorConfig(
                options=list(NOTICE_TYPES),
                multiple=True,
                custom_value=True,
                mode=SelectSelectorMode.DROPDOWN,
            )
        ),
        probatio.Required(CONF_DAYS): NumberSelector(
            NumberSelectorConfig(
                min=1,
                max=MAX_DAYS,
                step=1,
                unit_of_measurement="d",
                mode=NumberSelectorMode.BOX,
            )
        ),
    }
)


class BekendmakingenConfigFlow(ConfigFlow, domain=DOMAIN):
    """Ask for a location, a radius and which notices to follow."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Add a location, by default the home of Home Assistant."""
        return await self._async_step_settings(
            "user",
            user_input,
            {
                CONF_NAME: f"Bekendmakingen {self.hass.config.location_name}",
                CONF_LOCATION: {
                    CONF_LATITUDE: self.hass.config.latitude,
                    CONF_LONGITUDE: self.hass.config.longitude,
                    CONF_RADIUS: DEFAULT_RADIUS,
                },
                CONF_DAYS: DEFAULT_DAYS,
            },
        )

    async def async_step_reconfigure(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Change the location, the radius or which notices to follow."""
        entry = self._get_reconfigure_entry()
        return await self._async_step_settings(
            "reconfigure",
            user_input,
            {
                CONF_NAME: entry.title,
                CONF_LOCATION: {
                    CONF_LATITUDE: entry.data[CONF_LATITUDE],
                    CONF_LONGITUDE: entry.data[CONF_LONGITUDE],
                    CONF_RADIUS: entry.data[CONF_RADIUS],
                },
                CONF_TYPES: entry.data[CONF_TYPES],
                CONF_DAYS: entry.data[CONF_DAYS],
            },
        )

    async def _async_step_settings(
        self, step_id: str, user_input: dict[str, Any] | None, defaults: dict[str, Any]
    ) -> ConfigFlowResult:
        """Ask for the settings and look up the municipalities around the location."""
        errors: dict[str, str] = {}
        if user_input is not None:
            location = user_input[CONF_LOCATION]
            latitude: float = location[CONF_LATITUDE]
            longitude: float = location[CONF_LONGITUDE]
            radius: float = location.get(CONF_RADIUS, DEFAULT_RADIUS)
            client = BekendmakingenClient(async_get_clientsession(self.hass))
            try:
                municipalities = await client.async_get_municipalities(
                    latitude, longitude, radius
                )
            except BekendmakingenError as err:
                _LOGGER.debug("Could not look up the municipalities: %s", err)
                errors["base"] = "cannot_connect"
            else:
                if not municipalities:
                    errors[CONF_LOCATION] = "outside_netherlands"
            if not errors:
                title: str = user_input[CONF_NAME].strip()
                data = {
                    CONF_LATITUDE: latitude,
                    CONF_LONGITUDE: longitude,
                    CONF_RADIUS: radius,
                    CONF_TYPES: user_input.get(CONF_TYPES, []),
                    CONF_DAYS: int(user_input[CONF_DAYS]),
                    CONF_MUNICIPALITIES: municipalities,
                }
                if self.source == SOURCE_RECONFIGURE:
                    return self.async_update_reload_and_abort(
                        self._get_reconfigure_entry(), title=title, data=data
                    )
                return self.async_create_entry(title=title, data=data)

        return self.async_show_form(
            step_id=step_id,
            data_schema=self.add_suggested_values_to_schema(
                SCHEMA, user_input or defaults
            ),
            errors=errors,
        )
