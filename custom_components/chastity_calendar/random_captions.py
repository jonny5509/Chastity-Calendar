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
    # Short, punchy reminders
    "Locked in. Focused. At peace.",
    "One promise, one day at a time.",
    "Steady mind, steady commitment.",
    "Patience is part of the practice.",
    "A small reminder of a meaningful choice.",
    "Calm, committed, and carrying on.",
    "Today, I choose consistency.",
    "My commitment, my pace.",
    # Light-hearted and funny
    "Status update: still keeping my promise!",
    "The lock says stay focused. Fair enough.",
    "Another day, another check-in with my favourite calendar.",
    "My plans are secure. Literally.",
    "Today's forecast: a chance of patience.",
    "The calendar checked in before my coffee did.",
    "Commitment level: still showing up.",
    "A little humour makes patience easier.",
    # Calm, clarity and motivation
    "Make space for calm and keep your priorities clear.",
    "Let today's choices reflect what matters to you.",
    "Quiet focus can be its own reward.",
    "You can be committed without being hard on yourself.",
    "Build the habit gently; let consistency do the work.",
    "A clear intention can steady an ordinary day.",
    "Choose patience over pressure.",
    "Your progress is yours to define.",
    # Long-term commitment
    "A lasting promise is renewed through everyday choices.",
    "Long-term commitment is built one ordinary day at a time.",
    "Let time strengthen the intention behind your choice.",
    "Today is another page in a commitment you chose.",
    "A meaningful vow deserves thoughtful care.",
    "Stay true to your intention, and kind to yourself.",
    "The years are made of days like this one.",
    "Commitment is a practice, not just a declaration.",
    # Evening and bedtime reflection
    "Let the day settle; take your calm into the night.",
    "End today with gratitude for the promises you kept.",
    "A quiet evening is a good time to reflect.",
    "Rest matters too; tomorrow brings another day.",
    "Set the day down and give yourself room to recharge.",
    "Let patience be the last thought of the day.",
    "Wind down, breathe deeply, and look after yourself.",
    "Today's effort is enough; make space for rest.",
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
    # Romantic and keyholder appreciation
    "Your care makes this promise feel shared, not solitary.",
    "I value the trust we build through honest conversations.",
    "Thank you for treating my commitment with care.",
    "The strongest bond leaves room for both voices to be heard.",
    "I appreciate the patience and understanding we offer each other.",
    "Our trust grows when we communicate openly.",
    "I am grateful for the care behind our shared choices.",
    "Affection and respect belong at the heart of every promise.",
    # Playful anticipation
    "A little anticipation gives today a playful spark.",
    "Still smiling, still patient, still keeping my promise.",
    "The waiting is easier when we can laugh together.",
    "A playful reminder to keep the day interesting.",
    "Patience can have a mischievous little grin.",
    "A wink, a reminder, and back to my day.",
    "Anticipation is sweeter when trust comes first.",
    "A little teasing works best with kindness and clear communication.",
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
