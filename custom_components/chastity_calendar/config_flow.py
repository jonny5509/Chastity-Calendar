"""Config flow for Chastity Calendar."""
from __future__ import annotations

import json

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.core import callback

from .const import CONF_EVENTS, DEFAULT_EVENTS, DOMAIN


class ChastityCalendarConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Chastity Calendar."""

    VERSION = 1

    async def async_step_user(self, user_input=None):
        """Set up the calendar."""
        if self._async_current_entries():
            return self.async_abort(reason="single_instance_allowed")

        if user_input is not None:
            return self.async_create_entry(
                title="Chastity Calendar",
                data={CONF_EVENTS: DEFAULT_EVENTS},
            )

        return self.async_show_form(step_id="user", data_schema=vol.Schema({}))

    @staticmethod
    @callback
    def async_get_options_flow(config_entry):
        """Return the options flow."""
        return ChastityCalendarOptionsFlow(config_entry)


class ChastityCalendarOptionsFlow(config_entries.OptionsFlow):
    """Allow editing the monthly event list as JSON."""

    def __init__(self, config_entry):
        self._config_entry = config_entry

    async def async_step_init(self, user_input=None):
        """Manage calendar options."""
        current = self._config_entry.options.get(
            CONF_EVENTS, self._config_entry.data.get(CONF_EVENTS, DEFAULT_EVENTS)
        )
        if user_input is not None:
            try:
                events = json.loads(user_input[CONF_EVENTS])
                if not isinstance(events, list) or not events:
                    raise ValueError("Events must be a non-empty JSON list")
                seen_months = set()
                for event in events:
                    if not isinstance(event, dict):
                        raise ValueError("Each event must be an object")
                    month = int(event["month"])
                    if month < 1 or month > 12:
                        raise ValueError("Month must be between 1 and 12")
                    if month in seen_months:
                        raise ValueError("Only one event per month is supported")
                    seen_months.add(month)
                    if not str(event.get("title", "")).strip():
                        raise ValueError("Each event needs a title")
                    event["month"] = month
                    event["title"] = str(event["title"]).strip()
                    event["description"] = str(event.get("description", ""))
                return self.async_create_entry(title="", data={CONF_EVENTS: events})
            except (ValueError, TypeError, KeyError, json.JSONDecodeError):
                return self.async_show_form(
                    step_id="init",
                    data_schema=vol.Schema({
                        vol.Required(CONF_EVENTS, default=json.dumps(current, indent=2)): str
                    }),
                    errors={"base": "invalid_events"},
                )

        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema({
                vol.Required(CONF_EVENTS, default=json.dumps(current, indent=2)): str
            }),
        )
