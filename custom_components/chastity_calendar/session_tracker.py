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
    CONF_SERVICES,
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
        # None means no successful status check yet; True/False means active/inactive.
        self.active_sessions: dict[str, bool] = {}
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
        enabled_services = set(options.get(CONF_SERVICES, self.entry.data.get(CONF_SERVICES, [])))
        additions: dict[str, dict[str, Any]] = {}
        # Keep one emoji per service/session so backfilled days look consistent.
        session_emojis = self.history.setdefault("_session_emojis", {})
        session_entries = self.history.setdefault("_sessions", {})
        session_entries_before = {key: dict(value) for key, value in session_entries.items()}

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
            session_entry = session_entries.setdefault(
                session_key,
                {
                    "service": service,
                    "start": start.isoformat(),
                    "start_time": start_time,
                    "emoji": emoji,
                },
            )
            if not session_entry.get("start_time") and start_time:
                session_entry["start_time"] = start_time
            day = start
            while day <= today:
                record = additions.setdefault(
                    day.isoformat(), {"emojis": set(), "services": set(), "start_times": set()}
                )
                record["emojis"].add(emoji)
                record["services"].add(service)
                if start_time:
                    record["start_times"].add(f"{service}: {start_time}")
                day += timedelta(days=1)

        status_changed = False

        def set_status(service: str, active: bool) -> None:
            nonlocal status_changed
            if self.active_sessions.get(service) != active:
                self.active_sessions[service] = active
                status_changed = True

        # EmlaLock: status 1 is an active session; timestamps are Unix seconds.
        user_id = options.get(CONF_EMLALOCK_USER_ID)
        emla_token = options.get(CONF_EMLALOCK_API_TOKEN)
        if "emlalock" in enabled_services and user_id and emla_token:
            try:
                payload = await self._get_json(
                    "https://api.emlalock.com/info",
                    params={"userid": user_id, "apikey": emla_token},
                )
                session = (payload or {}).get("chastitysession") or {}
                active = int(session.get("status", 0)) == 1
                set_status("emlalock", active)
                if active:
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
        if "chastify" in enabled_services and chastify_token:
            try:
                payload = await self._get_json(
                    "https://chastify.net/api/apps/v1/session",
                    headers={"Authorization": f"Bearer {chastify_token}"},
                )
                lock = (payload or {}).get("lock") or {}
                set_status("chastify", bool(lock))
                if lock:
                    stamp = (
                        lock.get("startDate")
                        or lock.get("startedAt")
                        or lock.get("start_date")
                        or lock.get("createdAt")
                        or lock.get("created")
                    )
                    start = self._parse_date(stamp) or today
                    await add_span(
                        "Chastify", start, str(lock.get("id") or stamp or start.isoformat()),
                        self._format_start_time(stamp),
                    )
            except (aiohttp.ClientError, ValueError, TypeError, KeyError) as err:
                _LOGGER.warning("Unable to refresh Chastify session status (%s)", type(err).__name__)

        # Chaster's public API returns the user's locks; only active, non-archived locks count.
        chaster_token = options.get(CONF_CHASTER_API_TOKEN)
        if "chaster" in enabled_services and chaster_token:
            try:
                payload = await self._get_json(
                    "https://api.chaster.app/locks",
                    headers={"Authorization": f"Bearer {chaster_token}"},
                )
                # The Public API may return a list directly or wrap locks in a result field.
                if isinstance(payload, list):
                    locks = payload
                elif isinstance(payload, dict):
                    lock_container = payload
                    # Some API responses nest the result list under a data object.
                    if isinstance(lock_container.get("data"), dict):
                        lock_container = lock_container["data"]
                    locks = next(
                        (lock_container[key] for key in ("items", "results", "locks")
                         if isinstance(lock_container.get(key), list)),
                        [],
                    )
                else:
                    locks = []
                active_locks = []
                for lock in locks:
                    if not isinstance(lock, dict):
                        continue
                    status = str(lock.get("status", "")).lower()
                    # Chaster reports ongoing locks as "locked" in its Public API.
                    active = lock.get("active") is True or status in {
                        "active", "running", "ongoing", "locked"
                    }
                    archived = (
                        lock.get("archived") is True
                        or lock.get("isArchived") is True
                        or bool(lock.get("archivedAt"))
                    )
                    if active and not archived:
                        active_locks.append(lock)
                set_status("chaster", bool(active_locks))
                for lock in active_locks:
                    stamp = lock.get("startDate") or lock.get("startedAt") or lock.get("createdAt")
                    start = self._parse_date(stamp) or today
                    await add_span(
                        "Chaster", start, str(lock.get("id") or lock.get("_id") or stamp or start.isoformat()),
                        self._format_start_time(stamp),
                    )
            except (aiohttp.ClientError, ValueError, TypeError, KeyError) as err:
                _LOGGER.warning("Unable to refresh Chaster session status (%s)", type(err).__name__)

        changed = status_changed or session_entries != session_entries_before
        for day, incoming in additions.items():
            record = self.history.setdefault(day, {"emoji": next(iter(incoming["emojis"]), "✨"), "services": []})
            existing_emojis = set(record.get("emojis", []))
            # Migrate the legacy single-emoji field when new session data arrives.
            if not existing_emojis and record.get("emoji"):
                existing_emojis.add(record["emoji"])
            merged_emojis = sorted(existing_emojis | incoming.get("emojis", set()))
            if merged_emojis != record.get("emojis", []):
                record["emojis"] = merged_emojis
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
                    parsed = dt_util.as_local(parsed)
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
        """Return one daily calendar event per tracked service/session."""
        result: list[dict[str, Any]] = []
        sessions_by_service: dict[str, list[tuple[str, dict[str, Any], date]]] = {}
        for session_key, session in self.history.get("_sessions", {}).items():
            try:
                session_start = date.fromisoformat(session["start"])
            except (KeyError, TypeError, ValueError):
                continue
            service = str(session.get("service", session_key.split(":", 1)[0]))
            sessions_by_service.setdefault(service, []).append(
                (session_key, session, session_start)
            )

        for day, record in sorted(self.history.items()):
            try:
                event_date = date.fromisoformat(day)
            except (TypeError, ValueError):
                # Metadata buckets such as _sessions and _session_emojis are not dates.
                continue
            if not start <= event_date < end:
                continue

            services = record.get("services", [])
            matched_sessions: list[tuple[str, dict[str, Any], date]] = []
            for service in services:
                candidates = [
                    item for item in sessions_by_service.get(str(service), [])
                    if item[2] <= event_date
                ]
                if candidates:
                    # A service can have multiple tracked sessions; preserve each
                    # distinct session rather than combining them into one summary.
                    matched_sessions.extend(candidates)

            if matched_sessions:
                seen: set[str] = set()
                for session_key, session, session_start in matched_sessions:
                    if session_key in seen:
                        continue
                    seen.add(session_key)
                    service = str(session.get("service", session_key.split(":", 1)[0]))
                    emoji = str(session.get("emoji", "✨"))
                    start_time = session.get("start_time")
                    summary = f"{emoji} {service} — Active session"
                    if event_date == session_start:
                        summary += " — started"
                        if start_time:
                            summary += f" {start_time}"
                    description = (
                        f"Session history for {service}. "
                        f"Session start date: {session_start.isoformat()}."
                    )
                    if start_time:
                        description += f" Local start time: {start_time}."
                    result.append({
                        "start": event_date,
                        "end": event_date + timedelta(days=1),
                        "summary": summary,
                        "description": description,
                    })
            else:
                # Keep old saved records visible when they predate per-session metadata.
                emojis = record.get("emojis") or [record.get("emoji", "✨")]
                service_text = ", ".join(str(service) for service in services) or "Unknown service"
                start_times = ", ".join(record.get("start_times", []))
                summary = f"{' '.join(emojis)} Active session — {service_text}"
                if start_times:
                    summary += f" — started {start_times}"
                result.append({
                    "start": event_date,
                    "end": event_date + timedelta(days=1),
                    "summary": summary,
                    "description": (
                        f"Legacy active-session history for {service_text}. "
                        "This saved calendar record is retained for compatibility."
                    ),
                })
        return sorted(result, key=lambda item: (item["start"], item["summary"]))
