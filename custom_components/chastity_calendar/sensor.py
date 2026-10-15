"""Sensors for daily completion points."""
from __future__ import annotations

from homeassistant.components.sensor import SensorEntity, SensorDeviceClass
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity import EntityCategory
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN
from .obedience_points import DAILY_POINTS, YEARLY_BONUS


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up the persistent daily-points sensor."""
    tracker = hass.data[DOMAIN]["points"][entry.entry_id]
    async_add_entities([DailyCompletionPointsSensor(entry, tracker)])


class DailyCompletionPointsSensor(SensorEntity):
    """Report the locally tracked points total and completion count."""

    _attr_has_entity_name = True
    _attr_name = "Completion points"
    _attr_icon = "mdi:star-circle"
    _attr_native_unit_of_measurement = "points"
    _attr_should_poll = False

    def __init__(self, entry: ConfigEntry, tracker) -> None:
        self._entry = entry
        self._tracker = tracker
        self._attr_unique_id = f"{entry.entry_id}_completion_points"

    @property
    def native_value(self) -> int:
        return int(self._tracker.data.get("total_points", 0))

    @property
    def extra_state_attributes(self) -> dict:
        completed = self._tracker.data.get("completed_days", [])
        return {
            "completed_days": len(completed),
            "daily_points": DAILY_POINTS,
            "yearly_bonus_points": YEARLY_BONUS,
            "yearly_bonus_awarded": bool(self._tracker.data.get("yearly_bonus_awarded", False)),
            "last_completed_date": completed[-1] if completed else None,
        }

    async def async_added_to_hass(self) -> None:
        """Refresh the entity when the tracker records a day."""
        self.async_on_remove(
            async_dispatcher_connect(
                self.hass,
                f"{DOMAIN}_points_updated_{self._entry.entry_id}",
                self.async_write_ha_state,
            )
        )
