"""Regression tests for Obedience sync retry behavior without a full HA runtime."""
from __future__ import annotations

import asyncio
import sys
import types
from datetime import datetime
from pathlib import Path


def _install_home_assistant_stubs() -> None:
    """Provide the small Home Assistant surface needed to import the tracker."""
    root = Path(__file__).resolve().parents[1]
    integration_path = root / "custom_components" / "chastity_calendar"

    custom_components = types.ModuleType("custom_components")
    custom_components.__path__ = [str(root / "custom_components")]
    sys.modules.setdefault("custom_components", custom_components)

    integration = types.ModuleType("custom_components.chastity_calendar")
    integration.__path__ = [str(integration_path)]
    sys.modules.setdefault("custom_components.chastity_calendar", integration)

    ha = types.ModuleType("homeassistant")
    ha.__path__ = []
    core = types.ModuleType("homeassistant.core")
    core.HomeAssistant = type("HomeAssistant", (), {})
    core.ServiceCall = type("ServiceCall", (), {})
    helpers = types.ModuleType("homeassistant.helpers")
    helpers.__path__ = []
    dispatcher = types.ModuleType("homeassistant.helpers.dispatcher")
    dispatcher.async_dispatcher_send = lambda *args, **kwargs: None
    storage = types.ModuleType("homeassistant.helpers.storage")

    class Store:
        def __init__(self, *args, **kwargs):
            pass

    storage.Store = Store
    util = types.ModuleType("homeassistant.util")
    util.__path__ = []
    dt = types.ModuleType("homeassistant.util.dt")
    dt.now = datetime.now

    for name, module in {
        "homeassistant": ha,
        "homeassistant.core": core,
        "homeassistant.helpers": helpers,
        "homeassistant.helpers.dispatcher": dispatcher,
        "homeassistant.helpers.storage": storage,
        "homeassistant.util": util,
        "homeassistant.util.dt": dt,
    }.items():
        sys.modules.setdefault(name, module)


_install_home_assistant_stubs()

from custom_components.chastity_calendar.obedience_points import ObediencePoints


class _Entry:
    entry_id = "test-entry"

    def __init__(self, data):
        self.data = data
        self.options = {}


class _Store:
    async def async_save(self, data):
        self.saved = data.copy()


def _tracker(options, data):
    tracker = ObediencePoints.__new__(ObediencePoints)
    tracker.hass = object()
    tracker.entry = _Entry(options)
    tracker.store = _Store()
    tracker.data = data
    calls = []

    async def increment(extension_id, secret, habit_id):
        calls.append(habit_id)

    tracker._increment_habit = increment
    return tracker, calls


def test_yearly_only_habit_can_be_retried():
    tracker, calls = _tracker(
        {
            "obedience_enabled": True,
            "obedience_extension_id": "extension",
            "obedience_secret": "secret",
            "obedience_yearly_habit_id": "yearly-habit",
        },
        {
            "completed_days": ["2026-01-01"],
            "total_points": 100,
            "yearly_bonus_awarded": True,
            "obedience_synced_days": [],
            "yearly_obedience_synced": False,
        },
    )

    result = asyncio.run(tracker.async_sync_missing_points())

    assert calls == ["yearly-habit"]
    assert result["eligible"] is True
    assert result["yearly_bonus_synced"] is True
    assert result["yearly_bonus_pending"] is False
    assert result["synced"] == 0
    assert result["failed"] == 0


def test_daily_retry_does_not_increment_a_date_twice():
    tracker, calls = _tracker(
        {
            "obedience_enabled": True,
            "obedience_extension_id": "extension",
            "obedience_secret": "secret",
            "obedience_daily_habit_id": "daily-habit",
        },
        {
            "completed_days": ["2026-01-01", "2026-01-02"],
            "total_points": 200,
            "yearly_bonus_awarded": False,
            "obedience_synced_days": ["2026-01-01"],
            "yearly_obedience_synced": False,
        },
    )

    result = asyncio.run(tracker.async_sync_missing_points())

    assert calls == ["daily-habit"]
    assert result["eligible"] is True
    assert result["missing_dates"] == ["2026-01-02"]
    assert result["synced"] == 1
    assert result["failed"] == 0
