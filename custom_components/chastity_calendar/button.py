"""Buttons for Chastity Calendar."""
from __future__ import annotations

import logging
import random

from homeassistant.components.button import ButtonEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import (
    CONF_MONTHLY_NOTIFICATION_DESTINATION,
    CONF_MONTHLY_NOTIFICATION_TARGETS,
    DOMAIN,
)
from .random_captions import get_captions

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the uplifting caption button."""
    async_add_entities([UpliftingCaptionButton(hass, entry)])


class UpliftingCaptionButton(ButtonEntity):
    """Send a random commitment caption when a little encouragement is needed."""

    _attr_has_entity_name = False
    _attr_icon = "mdi:heart"
    _attr_should_poll = False

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        self.hass = hass
        self.entry = entry
        self._attr_name = f"{entry.title} — Send an uplifting caption"
        self._attr_unique_id = f"{entry.entry_id}_uplifting_caption"

    async def async_press(self) -> None:
        """Send one random caption through the configured notification destination."""
        settings = {**self.entry.data, **self.entry.options}
        destination = settings.get(
            CONF_MONTHLY_NOTIFICATION_DESTINATION, "home_assistant"
        )
        targets = settings.get(CONF_MONTHLY_NOTIFICATION_TARGETS, [])
        message = random.choice(get_captions(settings))
        title = f"{self.entry.title} — A Little Encouragement"
        delivered = False

        if destination in ("home_assistant", "both"):
            try:
                await self.hass.services.async_call(
                    "persistent_notification",
                    "create",
                    {
                        "title": title,
                        "message": message,
                        "notification_id": f"{DOMAIN}_{self.entry.entry_id}_uplifting_caption",
                    },
                    blocking=True,
                )
                delivered = True
            except Exception:
                _LOGGER.exception("Could not create the uplifting caption notification")

        if destination in ("phone", "both") and targets:
            try:
                await self.hass.services.async_call(
                    "notify",
                    "send_message",
                    {"title": title, "message": message},
                    target={"entity_id": targets},
                    blocking=True,
                )
                delivered = True
            except Exception:
                _LOGGER.exception("Could not send the uplifting caption phone notification")

        if not delivered:
            _LOGGER.warning(
                "No uplifting caption was delivered; check the notification destination and targets"
            )
