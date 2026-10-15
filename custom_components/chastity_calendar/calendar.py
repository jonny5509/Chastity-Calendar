"""Calendar platform for Chastity Calendar."""
from __future__ import annotations

from datetime import date, datetime
from typing import Any

from homeassistant.components.calendar import CalendarEntity, CalendarEvent
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import CONF_EVENTS, DEFAULT_EVENTS


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the calendar entity."""
    events = entry.options.get(CONF_EVENTS, entry.data.get(CONF_EVENTS, DEFAULT_EVENTS))
    async_add_entities([ChastityCalendar(entry, events)])


class ChastityCalendar(CalendarEntity):
    """A local calendar with one configurable all-day event per month."""

    _attr_has_entity_name = True
    _attr_name = "Monthly themes"
    _attr_icon = "mdi:calendar-heart"
    _attr_should_poll = False

    def __init__(self, entry: ConfigEntry, events: list[dict[str, Any]]) -> None:
        self._entry = entry
        self._events = events
        self._attr_unique_id = f"{entry.entry_id}_monthly_themes"

    @property
    def event(self) -> CalendarEvent | None:
        """Return the current or next upcoming event."""
        today = date.today()
        candidates = self._events_between(date(today.year, 1, 1), date(today.year + 3, 1, 1))
        for event in candidates:
            if event.start >= today or event.start <= today < event.end:
                return event
        return None

    async def async_get_events(
        self, hass: HomeAssistant, start_date: datetime, end_date: datetime
    ) -> list[CalendarEvent]:
        """Return all events in the requested range."""
        return self._events_between(start_date.date(), end_date.date())

    def _events_between(self, start: date, end: date) -> list[CalendarEvent]:
        """Expand month themes into all-day calendar events."""
        output: list[CalendarEvent] = []
        for year in range(start.year, end.year + 1):
            for item in self._events:
                month = int(item["month"])
                event_start = date(year, month, 1)
                event_end = date(year + (month == 12), 1 if month == 12 else month + 1, 1)
                if event_end > start and event_start < end:
                    output.append(
                        CalendarEvent(
                            start=event_start,
                            end=event_end,
                            summary=str(item["title"]),
                            description=str(item.get("description", "")),
                        )
                    )
        return sorted(output, key=lambda event: event.start)
