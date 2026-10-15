"""Chastity Calendar integration."""
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.const import Platform
from .const import DOMAIN
from .session_tracker import SessionHistory

PLATFORMS = [Platform.CALENDAR]

async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up calendar and persistent session history."""
    history = SessionHistory(hass, entry)
    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = history
    await history.async_start()
    entry.async_on_unload(entry.add_update_listener(_async_options_updated))
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True

async def _async_options_updated(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Reload when API tokens or polling settings change."""
    await hass.config_entries.async_reload(entry.entry_id)

async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload platforms and stop polling; history remains in HA storage."""
    if not await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        return False
    history = hass.data.get(DOMAIN, {}).pop(entry.entry_id, None)
    if history:
        await history.async_stop()
    return True
