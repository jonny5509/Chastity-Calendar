"""Random daily commitment-caption notifications."""
from __future__ import annotations

import logging
import random
from datetime import datetime

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.event import async_track_time_change
from homeassistant.helpers.storage import Store
from homeassistant.util import dt as dt_util

from .const import (
    CONF_MONTHLY_NOTIFICATION_DESTINATION,
    CONF_MONTHLY_NOTIFICATION_TARGETS,
    CONF_RANDOM_CAPTIONS_ENABLED,
    CONF_RELATIONSHIP_CAPTIONS_ENABLED,
    DOMAIN,
)

_LOGGER = logging.getLogger(__name__)

CAPTIONS = (
    "The lock is closed for good. My promise stays with it.",
    "No end date, no exit plan. Just a steady, lifelong vow.",
    "Forever is not too long. It is exactly how long I chose.",
    "I made this choice with a clear mind. I renew it every single day.",
    "Some promises are for a season. Mine is for a lifetime.",
    "The key is gone from my hands. My peace is not.",
    "I chose the long road. I walk it without regret.",
    "Permanence is not a punishment. It is my purpose.",
    "Years pass and my vow stays. That is a real commitment.",
    "I don't count the days anymore. I just live the promise.",
    "My word is locked in. So is my loyalty.",
    "Lifelong means every morning. I wake up and choose it again.",
    "This is not a phase. This is who I am now.",
    "Quiet, steady, and forever. That is my vow.",
    "I gave up the key. I gained a calm life.",
    "Devotion lasts longer than desire. That is why I stay.",
    "One decision, a whole lifetime. I would make it again.",
    "Locked in heart and in will. Committed for all my days.",
    # Discipline and patience
    "Progress comes from patience, not rushing.",
    "Today is an opportunity to practise self-control.",
    "Small acts of discipline build lasting habits.",
    "Stay focused on the reasons you started.",
    "Patience is a strength worth practising.",
    "A quiet day can still be a meaningful achievement.",
    "Consistency matters more than perfection.",
    "Take a breath, stay grounded and enjoy the journey.",
    # Playful reminders
    "Your daily reminder has arrived. You know the drill!",
    "Another day, another reason to smile at your commitment.",
    "Consider this your friendly little reminder.",
    "The calendar has spoken. Time to check in!",
    "Commitment check: still showing up?",
    "A little reminder to keep your promises to yourself.",
    "Your future self will appreciate today's consistency.",
    "No skipping today's reminder. The calendar remembers!",
    # Milestones and encouragement
    "One more day completed. Take a moment to recognise your consistency.",
    "A week of commitment is worth celebrating.",
    "Every milestone starts with a single day.",
    "Look how far you've come. Recognise your progress.",
    "Today marks another step along your journey.",
    "Celebrate progress, not just the final destination.",
    "Your consistency deserves a moment of appreciation.",
    "Every milestone tells a story of patience and perseverance.",
    # Personal wellbeing check-ins
    "How are you feeling about your commitment today?",
    "Take a moment to check in with yourself.",
    "Remember to make time for your wellbeing today.",
    "A good commitment includes listening to yourself.",
    "Stay hydrated, take a break and look after yourself.",
    "It's okay to reassess your goals as life changes.",
    "Progress should support your wellbeing, not come at its expense.",
    "Today's reminder: your comfort and wellbeing matter.",
)

# These are deliberately separate and disabled by default. They only join the
# random pool when the user explicitly enables relationship-focused captions.
RELATIONSHIP_CAPTIONS = (
    "Trust is built through honesty, communication and care.",
    "A meaningful commitment should always leave room for an honest conversation.",
    "Devotion means showing up with care and intention.",
    "Respect the promise, respect the people involved.",
    "Strong commitments are supported by mutual trust.",
    "Honesty makes a commitment stronger.",
    "A healthy dynamic begins with communication and consent.",
    "Commitment and self-respect can grow together.",
)


def get_captions(settings: dict) -> tuple[str, ...]:
    """Return captions, including relationship-focused ones only when enabled."""
    if settings.get(CONF_RELATIONSHIP_CAPTIONS_ENABLED, False):
        return CAPTIONS + RELATIONSHIP_CAPTIONS
    return CAPTIONS


async def async_setup_random_captions(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Send one randomly selected caption at a random time each enabled day."""
    settings = {**entry.data, **entry.options}
    if not settings.get(CONF_RANDOM_CAPTIONS_ENABLED, False):
        return

    store = Store(hass, 1, f"{DOMAIN}_{entry.entry_id}_random_captions")
    saved = await store.async_load() or {}
    state = {
        "scheduled_date": saved.get("scheduled_date"),
        "scheduled_minute": saved.get("scheduled_minute"),
        "last_sent_date": saved.get("last_sent_date"),
    }

    def ensure_schedule(now: datetime) -> None:
        date_key = now.date().isoformat()
        if state["scheduled_date"] != date_key:
            state["scheduled_date"] = date_key
            # Random local time between 09:00 and 21:59.
            state["scheduled_minute"] = random.randint(9 * 60, 21 * 60 + 59)
            hass.async_create_task(store.async_save(state.copy()))

    async def check_and_send(now: datetime) -> None:
        ensure_schedule(now)
        date_key = now.date().isoformat()
        if state["last_sent_date"] == date_key:
            return
        if now.hour * 60 + now.minute != state["scheduled_minute"]:
            return

        current = {**entry.data, **entry.options}
        destination = current.get(CONF_MONTHLY_NOTIFICATION_DESTINATION, "home_assistant")
        targets = current.get(CONF_MONTHLY_NOTIFICATION_TARGETS, [])
        message = random.choice(get_captions(current))
        delivered = False

        if destination in ("home_assistant", "both"):
            try:
                await hass.services.async_call(
                    "persistent_notification", "create",
                    {
                        "title": "Chastity Calendar — Daily Reminder",
                        "message": message,
                        "notification_id": f"{DOMAIN}_{entry.entry_id}_random_caption",
                    },
                    blocking=True,
                )
                delivered = True
            except Exception:
                _LOGGER.exception("Could not create the random caption notification")

        if destination in ("phone", "both") and targets:
            try:
                await hass.services.async_call(
                    "notify", "send_message",
                    {"title": "Chastity Calendar — Daily Reminder", "message": message},
                    target={"entity_id": targets},
                    blocking=True,
                )
                delivered = True
            except Exception:
                _LOGGER.exception("Could not send the random caption phone notification")

        if delivered:
            state["last_sent_date"] = date_key
            await store.async_save(state.copy())

    def tick(now: datetime) -> None:
        hass.async_create_task(check_and_send(now))

    ensure_schedule(dt_util.now())
    entry.async_on_unload(
        async_track_time_change(hass, tick, hour=None, minute=None, second=0)
    )
