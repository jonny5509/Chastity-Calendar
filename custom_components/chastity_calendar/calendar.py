"""Calendar platform for Chastity Calendar."""
from __future__ import annotations
from datetime import date, datetime
from typing import Any
from homeassistant.components.calendar import CalendarEntity, CalendarEvent
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from .const import CONF_EVENTS, DEFAULT_EVENTS, DOMAIN

async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback) -> None:
    """Set up calendar entity."""
    events = entry.options.get(CONF_EVENTS, entry.data.get(CONF_EVENTS, DEFAULT_EVENTS))
    async_add_entities([ChastityCalendar(hass, entry, events)])

class ChastityCalendar(CalendarEntity):
    """Calendar with monthly themes and append-only daily session records."""
    _attr_has_entity_name = True
    _attr_name = "Monthly themes and session history"
    _attr_icon = "mdi:calendar-heart"
    _attr_should_poll = False

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry, events: list[dict[str, Any]]) -> None:
        self._hass = hass
        self._entry = entry
        self._events = events
        self._attr_unique_id = f"{entry.entry_id}_monthly_themes"
        self._unsub_history = hass.bus.async_listen(f"{DOMAIN}_history_updated", self._history_updated)

    async def async_will_remove_from_hass(self) -> None:
        """Remove event listener."""
        self._unsub_history()

    async def _history_updated(self, event) -> None:
        if event.data.get("entry_id") == self._entry.entry_id:
            self.async_write_ha_state()

    @property
    def event(self) -> CalendarEvent | None:
        today = date.today()
        candidates = self._events_between(date(today.year, 1, 1), date(today.year + 3, 1, 1))
        for event in candidates:
            if event.start >= today or event.start <= today < event.end:
                return event
        return None

    async def async_get_events(self, hass: HomeAssistant, start_date: datetime, end_date: datetime) -> list[CalendarEvent]:
        """Return monthly themes and saved daily session events."""
        return self._events_between(start_date.date(), end_date.date())

    @callback
    def _events_between(self, start: date, end: date) -> list[CalendarEvent]:
        output: list[CalendarEvent] = []
        for year in range(start.year, end.year + 1):
            for item in self._events:
                month = int(item["month"])
                event_start = date(year, month, 1)
                event_end = date(year + (month == 12), 1 if month == 12 else month + 1, 1)
                if event_end > start and event_start < end:
                    output.append(CalendarEvent(start=event_start, end=event_end, summary=str(item["title"]), description=str(item.get("description", ""))))
        history = self._hass.data.get(DOMAIN, {}).get(self._entry.entry_id)
        if history:
            for item in history.events_between(start, end):
                output.append(CalendarEvent(start=item["start"], end=item["end"], summary=item["summary"], description=item["description"]))
        return sorted(output, key=lambda item: item.start)
