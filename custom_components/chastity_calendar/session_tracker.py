"""Poll configured services and persist a permanent day-by-day session history."""
from __future__ import annotations

import logging
import random
from datetime import date, datetime, timedelta
from typing import Any

import aiohttp
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.event import async_track_time_interval
from homeassistant.helpers.storage import Store
from homeassistant.util import dt as dt_util

from .const import (
    CONF_CHASTER_API_TOKEN,
    CONF_CHASTIFY_DEV_TOKEN,
    CONF_EMLALOCK_API_TOKEN,
    CONF_EMLALOCK_USER_ID,
    CONF_POLL_MINUTES,
    DOMAIN,
    EMOJIS,
)

_LOGGER = logging.getLogger(__name__)
STORAGE_VERSION = 1


class SessionHistory:
    """Own API polling and append-only history storage."""

    def __init__(self, hass: HomeAssistant, entry) -> None:
        self.hass = hass
        self.entry = entry
        self.store = Store(hass, STORAGE_VERSION, f"{DOMAIN}_{entry.entry_id}_history")
        self.history: dict[str, dict[str, Any]] = {}
        self._unsub = None
        self._session: aiohttp.ClientSession | None = None

    async def async_start(self) -> None:
        """Load stored history and start periodic refresh."""
        self.history = await self.store.async_load() or {}
        self._session = aiohttp.ClientSession()
        await self.async_refresh()
        minutes = int(self.entry.options.get(CONF_POLL_MINUTES, 5))
        self._unsub = async_track_time_interval(
            self.hass, self._async_interval, timedelta(minutes=minutes)
        )

    async def async_stop(self) -> None:
        """Stop polling without deleting history."""
        if self._unsub:
            self._unsub()
            self._unsub = None
        if self._session:
            await self._session.close()
            self._session = None

    async def _async_interval(self, _now) -> None:
        await self.async_refresh()

    async def _get_json(self, url: str, *, headers=None, params=None):
        """Fetch JSON without logging credentials or response bodies."""
        assert self._session is not None
        async with self._session.get(
            url, headers=headers, params=params, timeout=aiohttp.ClientTimeout(total=15)
        ) as response:
            if response.status == 404 or response.status == 409:
                return None
            response.raise_for_status()
            return await response.json(content_type=None)

    async def async_refresh(self) -> None:
        """Mark days from active sessions; preserve all previously recorded days."""
        options = self.entry.options
        today = dt_util.now().date()
        additions: dict[str, dict[str, Any]] = {}
        # Keep one emoji per service/session so backfilled days look consistent.
        session_emojis = self.history.setdefault("_session_emojis", {})

        async def add_span(
            service: str,
            start: date | None,
            session_id: str | None = None,
            start_time: str | None = None,
        ) -> None:
            if start is None or start > today:
                return
            session_key = f"{service}:{session_id or start.isoformat()}"
            emoji = session_emojis.setdefault(session_key, random.choice(EMOJIS))
            day = start
            while day <= today:
                record = additions.setdefault(
                    day.isoformat(), {"emoji": emoji, "services": set(), "start_times": set()}
                )
                record["services"].add(service)
                if start_time:
                    record["start_times"].add(f"{service}: {start_time}")
                day += timedelta(days=1)

        # EmlaLock: status 1 is an active session; timestamps are Unix seconds.
        user_id = options.get(CONF_EMLALOCK_USER_ID)
        emla_token = options.get(CONF_EMLALOCK_API_TOKEN)
        if user_id and emla_token:
            try:
                payload = await self._get_json(
                    "https://api.emlalock.com/info",
                    params={"userid": user_id, "apikey": emla_token},
                )
                session = (payload or {}).get("chastitysession") or {}
                if int(session.get("status", 0)) == 1:
                    stamp = session.get("startdate") or session.get("created")
                    start = self._parse_date(stamp) or today
                    await add_span(
                        "EmlaLock", start, str(session.get("id") or stamp or start.isoformat()),
                        self._format_start_time(stamp),
                    )
            except (aiohttp.ClientError, ValueError, TypeError, KeyError) as err:
                _LOGGER.warning("Unable to refresh EmlaLock session status (%s)", type(err).__name__)

        # Chastify's user-wide developer token exposes the current session endpoint.
        chastify_token = options.get(CONF_CHASTIFY_DEV_TOKEN)
        if chastify_token:
            try:
                payload = await self._get_json(
                    "https://chastify.net/api/apps/v1/session",
                    headers={"Authorization": f"Bearer {chastify_token}"},
                )
                lock = (payload or {}).get("lock") or {}
                if lock:
                    stamp = lock.get("startDate") or lock.get("startedAt") or lock.get("createdAt")
                    start = self._parse_date(stamp) or today
                    await add_span(
                        "Chastify", start, str(lock.get("id") or stamp or start.isoformat()),
                        self._format_start_time(stamp),
                    )
            except (aiohttp.ClientError, ValueError, TypeError, KeyError) as err:
                _LOGGER.warning("Unable to refresh Chastify session status (%s)", type(err).__name__)

        # Chaster's public API returns the user's locks; only active, non-archived locks count.
        chaster_token = options.get(CONF_CHASTER_API_TOKEN)
        if chaster_token:
            try:
                payload = await self._get_json(
                    "https://api.chaster.app/locks",
                    headers={"Authorization": f"Bearer {chaster_token}"},
                )
                locks = payload if isinstance(payload, list) else (payload or {}).get("items", [])
                for lock in locks or []:
                    if not isinstance(lock, dict):
                        continue
                    status = str(lock.get("status", "")).lower()
                    active = lock.get("active") is True or status in {"active", "running", "ongoing"}
                    if active and not lock.get("archived", False):
                        stamp = lock.get("startDate") or lock.get("startedAt") or lock.get("createdAt")
                        start = self._parse_date(stamp) or today
                        await add_span(
                            "Chaster", start, str(lock.get("id") or stamp or start.isoformat()),
                            self._format_start_time(stamp),
                        )
            except (aiohttp.ClientError, ValueError, TypeError, KeyError) as err:
                _LOGGER.warning("Unable to refresh Chaster session status (%s)", type(err).__name__)

        changed = False
        for day, incoming in additions.items():
            record = self.history.setdefault(day, {"emoji": incoming["emoji"], "services": []})
            if "emoji" not in record:
                record["emoji"] = incoming["emoji"]
                changed = True
            existing = set(record.get("services", []))
            merged = sorted(existing | incoming["services"])
            if merged != record.get("services", []):
                record["services"] = merged
                changed = True
            existing_times = set(record.get("start_times", []))
            merged_times = sorted(existing_times | incoming.get("start_times", set()))
            if merged_times != record.get("start_times", []):
                record["start_times"] = merged_times
                changed = True
        # Persist the session-to-emoji mapping even if every date already existed.
        if session_emojis and not self.history.get("_session_emojis_saved"):
            self.history["_session_emojis_saved"] = True
            changed = True
        if changed:
            await self.store.async_save(self.history)
            self.hass.bus.async_fire(f"{DOMAIN}_history_updated", {"entry_id": self.entry.entry_id})

    @staticmethod
    def _format_start_time(value: Any) -> str | None:
        """Format a session's start clock time for calendar display."""
        if value is None:
            return None
        try:
            if isinstance(value, (int, float)):
                parsed = datetime.fromtimestamp(value, dt_util.DEFAULT_TIME_ZONE)
            elif isinstance(value, str):
                parsed = dt_util.parse_datetime(value)
                if parsed is None:
                    parsed = datetime.fromtimestamp(float(value), dt_util.DEFAULT_TIME_ZONE)
                elif parsed.tzinfo is None:
                    parsed = parsed.replace(tzinfo=dt_util.DEFAULT_TIME_ZONE)
            else:
                return None
            return parsed.strftime("%H:%M")
        except (ValueError, TypeError, OSError, OverflowError):
            return None

    @staticmethod
    def _parse_date(value: Any) -> date | None:
        """Parse common API ISO timestamps or Unix timestamps."""
        if value is None:
            return None
        try:
            if isinstance(value, (int, float)):
                return datetime.fromtimestamp(value, dt_util.DEFAULT_TIME_ZONE).date()
            if isinstance(value, str):
                try:
                    return dt_util.parse_datetime(value).date()
                except (AttributeError, TypeError):
                    return datetime.fromtimestamp(float(value), dt_util.DEFAULT_TIME_ZONE).date()
        except (ValueError, TypeError, OSError, OverflowError):
            return None
        return None

    @callback
    def events_between(self, start: date, end: date) -> list[dict[str, Any]]:
        """Return persisted daily events in the requested date range."""
        result = []
        for day, record in sorted(self.history.items()):
            try:
                event_date = date.fromisoformat(day)
            except ValueError:
                continue
            if start <= event_date < end:
                services = ", ".join(record.get("services", []))
                start_times = ", ".join(record.get("start_times", []))
                summary = f"{record.get('emoji', '✨')} Active session"
                if start_times:
                    summary = f"{summary} — started {start_times}"
                description = f"Active session detected: {services}. This calendar record is permanent."
                if start_times:
                    description += f" Session start time(s): {start_times} (local time)."
                result.append({
                    "start": event_date,
                    "end": event_date + timedelta(days=1),
                    "summary": summary,
                    "description": description,
                })
        return result
