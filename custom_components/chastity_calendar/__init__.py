"""Chastity Calendar integration."""
from __future__ import annotations

import logging
from datetime import datetime

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.const import Platform
import voluptuous as vol
from homeassistant.helpers import config_validation as cv
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
from .obedience_points import ObediencePoints
from .random_captions import async_setup_random_captions

PLATFORMS = [Platform.CALENDAR, Platform.BINARY_SENSOR, Platform.SENSOR, Platform.BUTTON]
_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up calendar, persistent session history, and monthly reminders."""
    from .session_tracker import SessionHistory

    points = ObediencePoints(hass, entry)
    history = SessionHistory(hass, entry, points)
    await points.async_load()
    domain_data = hass.data.setdefault(DOMAIN, {})
    domain_data[entry.entry_id] = history
    domain_data.setdefault("points", {})[entry.entry_id] = points
    await history.async_start()
    entry.async_on_unload(entry.add_update_listener(_async_options_updated))
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    await _async_setup_monthly_notification(hass, entry)
    await async_setup_random_captions(hass, entry)

    def get_instance_tracker(call):
        """Resolve one tracker by setup name; never mix account data."""
        trackers = hass.data.get(DOMAIN, {}).get("points", {})
        requested_name = call.data.get("instance_name")
        entries = {
            config_entry.entry_id: config_entry
            for config_entry in hass.config_entries.async_entries(DOMAIN)
        }
        if requested_name:
            matches = [
                tracker for entry_id, tracker in trackers.items()
                if entry_id in entries and entries[entry_id].title == requested_name
            ]
            if len(matches) == 1:
                return matches[0]
            raise vol.Invalid(
                f"No unique Chastity Calendar setup named '{requested_name}' was found."
            )
        if len(trackers) == 1:
            return next(iter(trackers.values()))
        raise vol.Invalid(
            "Specify instance_name when more than one Chastity Calendar setup is configured."
        )

    if not hass.services.has_service(DOMAIN, "mark_day_complete"):
        async def mark_day_complete(call):
            """Record a completed day for the selected integration entry only."""
            await get_instance_tracker(call).async_mark_complete(call)

        hass.services.async_register(
            DOMAIN,
            "mark_day_complete",
            mark_day_complete,
            schema=vol.Schema({
                vol.Optional("date"): cv.date,
                vol.Optional("instance_name"): cv.string,
            }),
        )
    if not hass.services.has_service(DOMAIN, "sync_missing_points"):
        async def sync_missing_points(call):
            """Retry missing Obedience syncs for the selected setup only."""
            tracker = get_instance_tracker(call)
            result = await tracker.async_sync_missing_points()
            if not result["eligible"]:
                message = "Obedience sync is disabled or no daily habit ID is configured."
            else:
                message = (
                    f"Found {len(result['missing_dates'])} locally completed date(s) "
                    f"not marked as synced; {result['synced']} synced and "
                    f"{result['failed']} still missing after this run."
                )
            await hass.services.async_call(
                "persistent_notification",
                "create",
                {
                    "title": f"{tracker.entry.title} — Obedience sync check",
                    "message": message,
                    "notification_id": f"{DOMAIN}_{tracker.entry.entry_id}_obedience_sync_check",
                },
                blocking=True,
            )

        hass.services.async_register(
            DOMAIN,
            "sync_missing_points",
            sync_missing_points,
            schema=vol.Schema({vol.Optional("instance_name"): cv.string}),
        )
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
                        "title": entry.title,
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
                    {"title": entry.title, "message": message},
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
        if now.day == 1:
            hass.async_create_task(send_reminder(now))

    # async_track_time_change supports time fields, but not a day-of-month field.
    # Run daily at this time and filter to the first day in the callback.
    entry.async_on_unload(
        async_track_time_change(
            hass, handle_month_change, hour=0, minute=0, second=5
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
    domain_data = hass.data.get(DOMAIN, {})
    history = domain_data.pop(entry.entry_id, None)
    domain_data.get("points", {}).pop(entry.entry_id, None)
    if history:
        await history.async_stop()
    return True
