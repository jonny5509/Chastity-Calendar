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
        }

    async def async_load(self) -> None:
        """Restore previously completed dates."""
        saved = await self.store.async_load()
        if isinstance(saved, dict):
            self.data.update(saved)
        if not isinstance(self.data.get("completed_days"), list):
            self.data["completed_days"] = []

    async def async_mark_complete(self, call: ServiceCall) -> None:
        """Record one completed day, awarding each date at most once."""
        raw_date = call.data.get("date")
        completed_date = raw_date if isinstance(raw_date, date) else dt_util.now().date()
        date_key = completed_date.isoformat()
        completed_days = set(self.data["completed_days"])
        if date_key in completed_days:
            _LOGGER.debug("Completion for %s was already recorded", date_key)
            return

        completed_days.add(date_key)
        self.data["completed_days"] = sorted(completed_days)
        self.data["total_points"] = len(completed_days) * DAILY_POINTS
        should_award_yearly = (
            len(completed_days) >= YEARLY_COMPLETIONS
            and not self.data.get("yearly_bonus_awarded", False)
        )
        if should_award_yearly or self.data.get("yearly_bonus_awarded", False):
            self.data["total_points"] += YEARLY_BONUS

        options = {**self.entry.data, **self.entry.options}
        extension_id = options.get(CONF_OBEDIENCE_EXTENSION_ID)
        secret = options.get(CONF_OBEDIENCE_SECRET)
        daily_habit = options.get(CONF_OBEDIENCE_DAILY_HABIT_ID)
        yearly_habit = options.get(CONF_OBEDIENCE_YEARLY_HABIT_ID)

        if extension_id and secret:
            try:
                if daily_habit:
                    await self._increment_habit(extension_id, secret, daily_habit)
                if should_award_yearly and yearly_habit:
                    await self._increment_habit(extension_id, secret, yearly_habit)
            except (aiohttp.ClientError, TimeoutError, ValueError) as err:
                _LOGGER.warning("Could not sync completion to Obedience: %s", err)
                await self.store.async_save(self.data)
        async_dispatcher_send(self.hass, f"{DOMAIN}_points_updated_{self.entry.entry_id}")
                return

        if should_award_yearly:
            self.data["yearly_bonus_awarded"] = True
        await self.store.async_save(self.data)

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
