"""Chastity Calendar integration."""
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.const import Platform
import voluptuous as vol
from homeassistant.helpers import config_validation as cv

from .const import DOMAIN
from .obedience_points import ObediencePoints
from .session_tracker import SessionHistory

PLATFORMS = [Platform.CALENDAR, Platform.BINARY_SENSOR, Platform.SENSOR]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up calendar, session history, and daily completion service."""
    history = SessionHistory(hass, entry)
    points = ObediencePoints(hass, entry)
    await points.async_load()
    domain_data = hass.data.setdefault(DOMAIN, {})
    domain_data[entry.entry_id] = history
    domain_data.setdefault("points", {})[entry.entry_id] = points
    await history.async_start()

    service_name = "mark_day_complete"
    if not hass.services.has_service(DOMAIN, service_name):
        async def mark_day_complete(call):
            """Record a completed day for each configured integration entry."""
            for point_tracker in hass.data.get(DOMAIN, {}).get("points", {}).values():
                await point_tracker.async_mark_complete(call)

        hass.services.async_register(
            DOMAIN,
            service_name,
            mark_day_complete,
            schema=vol.Schema({vol.Optional("date"): cv.date}),
        )
    entry.async_on_unload(entry.add_update_listener(_async_options_updated))
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def _async_options_updated(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Reload when API tokens or polling settings change."""
    await hass.config_entries.async_reload(entry.entry_id)


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload platforms and stop polling; saved history and points remain in storage."""
    if not await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        return False
    domain_data = hass.data.get(DOMAIN, {})
    history = domain_data.pop(entry.entry_id, None)
    domain_data.get("points", {}).pop(entry.entry_id, None)
    if history:
        await history.async_stop()
    return True
