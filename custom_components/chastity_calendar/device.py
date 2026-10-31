"""Shared Home Assistant device metadata for Chastity Calendar."""
from __future__ import annotations

from homeassistant.helpers.device_registry import DeviceInfo

from .const import DOMAIN


def get_device_info(entry) -> DeviceInfo:
    """Return the shared device identity used by every integration entity."""
    return DeviceInfo(
        identifiers={(DOMAIN, entry.entry_id)},
        name="Chastity Calendar",
        manufacturer="Chastity Calendar",
        model="Chastity Calendar",
    )
