"""Chastity Calendar integration."""
from __future__ import annotations

import logging
from datetime import datetime

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.const import Platform
from homeassistant.helpers.event import async_track_time_change
from homeassistant.helpers.storage import Store
from homeassistant.util import dt as dt_util

from .const import (
    CONF_EVENTS,
    CONF_MONTHLY_NOTIFICATION_DESTINATION,
    CONF_MONTHLY_NOTIFICATION_TARGETS,
    DEFAULT_EVENTS,
    DOMAIN,
)

PLATFORMS = [Platform.CALENDAR, Platform.BINARY_SENSOR]
_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up calendar, persistent session history, and monthly reminders."""
    from .session_tracker import SessionHistory

    history = SessionHistory(hass, entry)
    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = history
    await history.async_start()
    entry.async_on_unload(entry.add_update_listener(_async_options_updated))
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    await _async_setup_monthly_notification(hass, entry)
    return True


async def _async_setup_monthly_notification(
    hass: HomeAssistant, entry: ConfigEntry
) -> None:
    """Send one configurable reminder at the beginning of each month."""
    store = Store(hass, 1, f"{DOMAIN}_{entry.entry_id}_monthly_notification")
    saved = await store.async_load() or {}
    state = {"last_notified_month": saved.get("last_notified_month")}

    async def send_reminder(now: datetime) -> None:
        month_key = now.strftime("%Y-%m")
        if state["last_notified_month"] == month_key:
            return

        settings = {**entry.data, **entry.options}
        events = settings.get(CONF_EVENTS, DEFAULT_EVENTS)
        theme = next(
            (
                str(item.get("title", "")).strip()
                for item in events
                if int(item.get("month", 0)) == now.month
                and str(item.get("title", "")).strip()
            ),
            now.strftime("%B"),
        )
        message = f"Are you ready for {theme}?"
        destination = settings.get(
            CONF_MONTHLY_NOTIFICATION_DESTINATION, "home_assistant"
        )
        targets = settings.get(CONF_MONTHLY_NOTIFICATION_TARGETS, [])
        delivered = False

        if destination in ("home_assistant", "both"):
            try:
                await hass.services.async_call(
                    "persistent_notification",
                    "create",
                    {
                        "title": "Chastity Calendar",
                        "message": message,
                        "notification_id": f"{DOMAIN}_{entry.entry_id}_monthly_theme",
                    },
                    blocking=True,
                )
                delivered = True
            except Exception:
                _LOGGER.exception("Could not create the monthly theme notification")

        if destination in ("phone", "both") and targets:
            try:
                await hass.services.async_call(
                    "notify",
                    "send_message",
                    {"title": "Chastity Calendar", "message": message},
                    target={"entity_id": targets},
                    blocking=True,
                )
                delivered = True
            except Exception:
                _LOGGER.exception("Could not send the monthly theme phone notification")

        if delivered:
            state["last_notified_month"] = month_key
            await store.async_save(state)

    def handle_month_change(now: datetime) -> None:
        """Run the reminder at local midnight on the first day of each month."""
        hass.async_create_task(send_reminder(now))

    entry.async_on_unload(
        async_track_time_change(
            hass, handle_month_change, day=1, hour=0, minute=0, second=5
        )
    )

    # If Home Assistant starts during the first day, don't miss that month's reminder.
    now = dt_util.now()
    if now.day == 1:
        await send_reminder(now)


async def _async_options_updated(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Reload when API tokens or notification settings change."""
    await hass.config_entries.async_reload(entry.entry_id)


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload platforms and stop polling; history remains in HA storage."""
    if not await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        return False
    history = hass.data.get(DOMAIN, {}).pop(entry.entry_id, None)
    if history:
        await history.async_stop()
    return True
