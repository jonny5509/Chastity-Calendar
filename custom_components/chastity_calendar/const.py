"""Constants for Chastity Calendar."""
DOMAIN = "chastity_calendar"
CONF_EVENTS = "events"
CONF_SERVICES = "services"
SERVICE_OPTIONS = {"emlalock": "EmlaLock", "chaster": "Chaster", "chastify": "Chastify"}
CONF_EMLALOCK_USER_ID = "emlalock_user_id"
CONF_EMLALOCK_API_TOKEN = "emlalock_api_token"
CONF_CHASTIFY_DEV_TOKEN = "chastify_dev_token"
CONF_CHASTER_API_TOKEN = "chaster_api_token"
CONF_POLL_MINUTES = "poll_minutes"
CONF_OBEDIENCE_ENABLED = "obedience_enabled"
CONF_OBEDIENCE_EXTENSION_ID = "obedience_extension_id"
CONF_OBEDIENCE_SECRET = "obedience_secret"
CONF_OBEDIENCE_DAILY_HABIT_ID = "obedience_daily_habit_id"
CONF_OBEDIENCE_YEARLY_HABIT_ID = "obedience_yearly_habit_id"
CONF_MONTHLY_NOTIFICATION_DESTINATION = "monthly_notification_destination"
CONF_MONTHLY_NOTIFICATION_TARGETS = "monthly_notification_targets"
CONF_RANDOM_CAPTIONS_ENABLED = "random_captions_enabled"
CONF_RELATIONSHIP_CAPTIONS_ENABLED = "relationship_captions_enabled"
NOTIFICATION_DESTINATIONS = {
    "home_assistant": "Home Assistant",
    "phone": "Phone notification(s)",
    "both": "Home Assistant and phone",
}
EMOJIS = ("👑", "💅", "👠", "💄", "✨", "🎀")
DEFAULT_EVENTS = [
    {"month": 1, "title": "Jailbird January", "description": "Community-themed chastity challenge. Set your own optional, consensual goals."},
    {"month": 2, "title": "Frustrated February", "description": "Community-themed denial challenge. Participation and rules are personal choices."},
    {"month": 3, "title": "Milking March", "description": "A community-themed challenge; customize the theme to your preferences."},
    {"month": 4, "title": "Abstinence April", "description": "A month-long abstinence prompt. Choose your own boundaries and duration."},
    {"month": 5, "title": "You May Not", "description": "A playful community-style challenge name; customize the rules or rename it."},
    {"month": 6, "title": "Jerk-NO June", "description": "An optional abstinence-themed challenge prompt."},
    {"month": 7, "title": "Juicy July", "description": "A community-style theme; use it for a challenge, check-in, or personal goal."},
    {"month": 8, "title": "Alternate August", "description": "A less standardized community theme. Customize or replace it."},
    {"month": 9, "title": "Sexless September", "description": "An optional abstinence-themed challenge prompt."},
    {"month": 10, "title": "Locktober", "description": "A popular month-long chastity community challenge. Participation is optional and consensual."},
    {"month": 11, "title": "No Nut November", "description": "A widely known internet abstinence challenge."},
    {"month": 12, "title": "Denial December", "description": "A community-style denial theme. Customize to your preferences."},
]
