"""Binary sensors indicating whether each connected service has an active session."""
from __future__ import annotations

from homeassistant.components.binary_sensor import BinarySensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import (
    CONF_CHASTER_API_TOKEN,
    CONF_CHASTIFY_DEV_TOKEN,
    CONF_EMLALOCK_API_TOKEN,
    CONF_EMLALOCK_USER_ID,
    CONF_SERVICES,
    DOMAIN,
    SERVICE_OPTIONS,
)


SERVICE_CREDENTIALS = {
    "emlalock": (CONF_EMLALOCK_USER_ID, CONF_EMLALOCK_API_TOKEN),
    "chaster": (CONF_CHASTER_API_TOKEN,),
    "chastify": (CONF_CHASTIFY_DEV_TOKEN,),
}


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Create one active-session binary sensor for each supported service."""
    history = hass.data[DOMAIN][entry.entry_id]
    async_add_entities(
        ServiceActiveSessionSensor(hass, entry, history, service)
        for service in SERVICE_OPTIONS
    )


class ServiceActiveSessionSensor(BinarySensorEntity):
    """Represent the active-session status of one service."""

    _attr_has_entity_name = True
    _attr_device_class = None

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry, history, service: str) -> None:
        self._hass = hass
        self._entry = entry
        self._history = history
        self._service = service
        self._attr_name = f"{SERVICE_OPTIONS[service]} active session"
        self._attr_unique_id = f"{entry.entry_id}_{service}_active_session"
        self._attr_icon = "mdi:lock-check"

    @property
    def is_on(self) -> bool | None:
        """Return true when the service reports an active session."""
        return self._history.active_sessions.get(self._service)

    @property
    def available(self) -> bool:
        """Only report a state after a selected service has been checked successfully."""
        enabled = set(
            self._entry.options.get(
                CONF_SERVICES, self._entry.data.get(CONF_SERVICES, [])
            )
        )
        if self._service not in enabled or self._service not in self._history.active_sessions:
            return False
        options = {**self._entry.data, **self._entry.options}
        return all(options.get(key) for key in SERVICE_CREDENTIALS[self._service])

    async def async_added_to_hass(self) -> None:
        """Listen for session status updates."""
        self._unsub = self._hass.bus.async_listen(
            f"{DOMAIN}_history_updated", self._handle_update
        )

    async def async_will_remove_from_hass(self) -> None:
        """Remove event listener."""
        if getattr(self, "_unsub", None):
            self._unsub()

    async def _handle_update(self, event) -> None:
        if event.data.get("entry_id") == self._entry.entry_id:
            self.async_write_ha_state()
