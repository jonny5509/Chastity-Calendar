"""Daily completion points with optional Obedience habit syncing."""
from __future__ import annotations

import logging
from datetime import date
from typing import Any

import aiohttp
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.helpers.dispatcher import async_dispatcher_send
from homeassistant.helpers.storage import Store
from homeassistant.util import dt as dt_util

from .const import (
    CONF_OBEDIENCE_DAILY_HABIT_ID,
    CONF_DAILY_POINTS,
    CONF_YEARLY_BONUS_POINTS,
    CONF_YEARLY_COMPLETIONS,
    CONF_OBEDIENCE_EXTENSION_ID,
    CONF_OBEDIENCE_SECRET,
    CONF_OBEDIENCE_YEARLY_HABIT_ID,
    DOMAIN,
)

_LOGGER = logging.getLogger(__name__)
DAILY_POINTS = 100
YEARLY_BONUS = 1095
YEARLY_COMPLETIONS = 365
STORE_VERSION = 1


class ObediencePoints:
    """Track completed calendar days and optionally increment Obedience habits."""

    def __init__(self, hass: HomeAssistant, entry) -> None:
        self.hass = hass
        self.entry = entry
        self.store = Store(hass, STORE_VERSION, f"{DOMAIN}_{entry.entry_id}_points")
        self.data: dict[str, Any] = {
            "completed_days": [],
            "total_points": 0,
            "yearly_bonus_awarded": False,
            "obedience_synced_days": [],
            "yearly_obedience_synced": False,
        }

    async def async_load(self) -> None:
        """Restore previously completed dates."""
        saved = await self.store.async_load()
        if isinstance(saved, dict):
            self.data.update(saved)
        for key in ("completed_days", "obedience_synced_days"):
            if not isinstance(self.data.get(key), list):
                self.data[key] = []

        # Backward compatibility with the previous tracker format.
        self.data.setdefault("yearly_obedience_synced", False)
        settings = {**self.entry.data, **self.entry.options}
        daily_points = int(settings.get(CONF_DAILY_POINTS, DAILY_POINTS))
        yearly_bonus = int(settings.get(CONF_YEARLY_BONUS_POINTS, YEARLY_BONUS))
        yearly_completions = int(settings.get(CONF_YEARLY_COMPLETIONS, YEARLY_COMPLETIONS))
        if len(self.data["completed_days"]) >= yearly_completions:
            self.data["yearly_bonus_awarded"] = True
        self.data["total_points"] = len(set(self.data["completed_days"])) * daily_points
        if self.data.get("yearly_bonus_awarded", False):
            self.data["total_points"] += yearly_bonus
        await self.store.async_save(self.data)

    async def async_mark_complete(self, call: ServiceCall) -> None:
        """Record a date once and retry any Obedience sync still pending for it."""
        raw_date = call.data.get("date")
        completed_date = raw_date if isinstance(raw_date, date) else dt_util.now().date()
        await self.async_mark_date(completed_date)

    async def async_mark_date(self, completed_date: date) -> None:
        """Record a specific date once, with the same persistence and sync behavior."""
        date_key = completed_date.isoformat()

        completed_days = set(self.data["completed_days"])
        is_new_completion = date_key not in completed_days
        if is_new_completion:
            completed_days.add(date_key)
            self.data["completed_days"] = sorted(completed_days)

        options = {**self.entry.data, **self.entry.options}
        daily_points = int(options.get(CONF_DAILY_POINTS, DAILY_POINTS))
        yearly_bonus = int(options.get(CONF_YEARLY_BONUS_POINTS, YEARLY_BONUS))
        yearly_completions = int(options.get(CONF_YEARLY_COMPLETIONS, YEARLY_COMPLETIONS))
        if len(completed_days) >= yearly_completions and not self.data.get("yearly_bonus_awarded", False):
            self.data["yearly_bonus_awarded"] = True
        self.data["total_points"] = len(completed_days) * daily_points
        if self.data.get("yearly_bonus_awarded", False):
            self.data["total_points"] += yearly_bonus

        extension_id = options.get(CONF_OBEDIENCE_EXTENSION_ID)
        secret = options.get(CONF_OBEDIENCE_SECRET)
        daily_habit = options.get(CONF_OBEDIENCE_DAILY_HABIT_ID)
        yearly_habit = options.get(CONF_OBEDIENCE_YEARLY_HABIT_ID)

        # Local completion is authoritative. Persist it before making network calls,
        # so a failed optional Obedience API request never loses the points.
        await self.store.async_save(self.data)

        if options.get("obedience_enabled", bool(extension_id and secret)) and extension_id and secret:
            try:
                synced_days = set(self.data["obedience_synced_days"])
                if daily_habit and date_key not in synced_days:
                    await self._increment_habit(extension_id, secret, daily_habit)
                    synced_days.add(date_key)
                    self.data["obedience_synced_days"] = sorted(synced_days)
                    await self.store.async_save(self.data)

                if (
                    self.data.get("yearly_bonus_awarded", False)
                    and yearly_habit
                    and not self.data.get("yearly_obedience_synced", False)
                ):
                    await self._increment_habit(extension_id, secret, yearly_habit)
                    self.data["yearly_obedience_synced"] = True
                    await self.store.async_save(self.data)
            except (aiohttp.ClientError, TimeoutError, ValueError) as err:
                _LOGGER.warning(
                    "Could not sync completion to Obedience; it can be retried "
                    "by calling mark_day_complete for the same date: %s",
                    err,
                )

        async_dispatcher_send(
            self.hass, f"{DOMAIN}_points_updated_{self.entry.entry_id}"
        )

    async def async_sync_missing_points(self) -> dict[str, Any]:
        """Retry Obedience sync for locally completed dates not yet acknowledged."""
        options = {**self.entry.data, **self.entry.options}
        daily_habit = options.get(CONF_OBEDIENCE_DAILY_HABIT_ID)
        extension_id = options.get(CONF_OBEDIENCE_EXTENSION_ID)
        secret = options.get(CONF_OBEDIENCE_SECRET)
        enabled = options.get("obedience_enabled", bool(extension_id and secret))
        if not enabled or not daily_habit or not extension_id or not secret:
            return {"eligible": False, "missing_dates": [], "synced": 0, "failed": 0}

        before = set(self.data.get("obedience_synced_days", []))
        missing = [
            item for item in sorted(set(self.data.get("completed_days", [])))
            if item not in before
        ]
        for item in missing:
            await self.async_mark_date(date.fromisoformat(item))
        after = set(self.data.get("obedience_synced_days", []))
        synced = len(after - before)
        return {
            "eligible": True,
            "missing_dates": missing,
            "synced": synced,
            "failed": len(missing) - synced,
        }

    async def _increment_habit(
        self, extension_id: str, secret: str, habit_id: str
    ) -> None:
        """Increment an eligible Obedience habit by one."""
        timeout = aiohttp.ClientTimeout(total=10)
        async with aiohttp.ClientSession(timeout=timeout) as session:
            async with session.post(
                "https://app.obedienceapp.com/extensions/habits",
                params={"extensionId": extension_id, "secret": secret, "id": habit_id},
                json={"action": "increment", "amount": 1},
            ) as response:
                if response.status >= 400:
                    raise ValueError(f"Obedience API returned HTTP {response.status}")
                await response.read()
