"""Config flow for Chastity Calendar."""
from __future__ import annotations
import json
import voluptuous as vol
from homeassistant import config_entries
from homeassistant.core import callback
from homeassistant.helpers import config_validation as cv
from .const import (
    CONF_CHASTER_API_TOKEN, CONF_CHASTIFY_DEV_TOKEN, CONF_EMLALOCK_API_TOKEN,
    CONF_EMLALOCK_USER_ID, CONF_EVENTS, CONF_POLL_MINUTES, CONF_SERVICES, SERVICE_OPTIONS, DEFAULT_EVENTS, DOMAIN,
)

class ChastityCalendarConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle config flow."""
    VERSION = 1

    async def async_step_user(self, user_input=None):
        """Set up calendar; service credentials are optional in the options page."""
        if self._async_current_entries():
            return self.async_abort(reason="single_instance_allowed")
        if user_input is not None:
            return self.async_create_entry(title="Chastity Calendar", data={CONF_EVENTS: DEFAULT_EVENTS, CONF_SERVICES: sorted(user_input[CONF_SERVICES])})
        return self.async_show_form(step_id="user", data_schema=vol.Schema({vol.Required(CONF_SERVICES, default=[]): cv.multi_select(SERVICE_OPTIONS)}))

    @staticmethod
    @callback
    def async_get_options_flow(config_entry):
        return ChastityCalendarOptionsFlow(config_entry)

class ChastityCalendarOptionsFlow(config_entries.OptionsFlow):
    """Edit monthly events and optional API credentials."""
    def __init__(self, config_entry):
        self._config_entry = config_entry

    async def async_step_init(self, user_input=None):
        current = {**self._config_entry.data, **self._config_entry.options}
        events = current.get(CONF_EVENTS, self._config_entry.data.get(CONF_EVENTS, DEFAULT_EVENTS))
        if user_input is not None:
            try:
                parsed = json.loads(user_input[CONF_EVENTS])
                if not isinstance(parsed, list) or not parsed:
                    raise ValueError
                months = set()
                for event in parsed:
                    if not isinstance(event, dict):
                        raise ValueError
                    month = int(event["month"])
                    if not 1 <= month <= 12 or month in months or not str(event.get("title", "")).strip():
                        raise ValueError
                    months.add(month)
                    event["month"] = month
                    event["title"] = str(event["title"]).strip()
                    event["description"] = str(event.get("description", ""))
                data = {CONF_EVENTS: parsed, CONF_SERVICES: sorted(user_input.get(CONF_SERVICES, []))}
                for key in (CONF_EMLALOCK_USER_ID, CONF_EMLALOCK_API_TOKEN, CONF_CHASTIFY_DEV_TOKEN, CONF_CHASTER_API_TOKEN):
                    data[key] = user_input.get(key, "").strip()
                data[CONF_POLL_MINUTES] = int(user_input[CONF_POLL_MINUTES])
                return self.async_create_entry(title="", data=data)
            except (ValueError, TypeError, KeyError, json.JSONDecodeError):
                return self.async_show_form(step_id="init", data_schema=self._schema(events, user_input), errors={"base": "invalid_options"})
        return self.async_show_form(step_id="init", data_schema=self._schema(events, current))

    @staticmethod
    def _schema(events, values):
        return vol.Schema({
            vol.Required(CONF_EVENTS, default=json.dumps(events, indent=2)): str,
            vol.Required(CONF_SERVICES, default=values.get(CONF_SERVICES, [])): cv.multi_select(SERVICE_OPTIONS),
            vol.Optional(CONF_EMLALOCK_USER_ID, default=values.get(CONF_EMLALOCK_USER_ID, "")): str,
            vol.Optional(CONF_EMLALOCK_API_TOKEN, default=values.get(CONF_EMLALOCK_API_TOKEN, "")): str,
            vol.Optional(CONF_CHASTIFY_DEV_TOKEN, default=values.get(CONF_CHASTIFY_DEV_TOKEN, "")): str,
            vol.Optional(CONF_CHASTER_API_TOKEN, default=values.get(CONF_CHASTER_API_TOKEN, "")): str,
            vol.Required(CONF_POLL_MINUTES, default=values.get(CONF_POLL_MINUTES, 5)): vol.All(int, vol.Range(min=1, max=60)),
        })
