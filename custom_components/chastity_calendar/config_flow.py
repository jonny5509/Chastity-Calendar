"""Config flow for Chastity Calendar."""
from __future__ import annotations

import json

import voluptuous as vol
from homeassistant import config_entries
from homeassistant.core import callback
from homeassistant.helpers import config_validation as cv

from .const import (
    CONF_CHASTER_API_TOKEN,
    CONF_CHASTIFY_DEV_TOKEN,
    CONF_EMLALOCK_API_TOKEN,
    CONF_EMLALOCK_USER_ID,
    CONF_EVENTS,
    CONF_POLL_MINUTES,
    CONF_SERVICES,
    SERVICE_OPTIONS,
    DEFAULT_EVENTS,
    DOMAIN,
)


SERVICE_ORDER = ("emlalock", "chaster", "chastify")


class ChastityCalendarConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle config flow."""

    VERSION = 1

    def __init__(self):
        self._selected_services = []
        self._service_data = {}

    async def async_step_user(self, user_input=None):
        """Select which services to configure."""
        if self._async_current_entries():
            return self.async_abort(reason="single_instance_allowed")
        if user_input is not None:
            self._selected_services = [
                service for service in SERVICE_ORDER
                if service in user_input.get(CONF_SERVICES, [])
            ]
            self._service_data = {
                CONF_EVENTS: DEFAULT_EVENTS,
                CONF_SERVICES: self._selected_services,
            }
            return await self._async_next_service(0)
        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema({
                vol.Required(CONF_SERVICES, default=[]): cv.multi_select(SERVICE_OPTIONS)
            }),
        )

    async def _async_next_service(self, index):
        """Show a credentials page only for each selected service."""
        if index >= len(self._selected_services):
            return self.async_create_entry(
                title="Chastity Calendar", data=self._service_data
            )
        service = self._selected_services[index]
        return await getattr(self, f"async_step_{service}")()

    async def async_step_emlalock(self, user_input=None):
        if user_input is not None:
            self._service_data.update({
                CONF_EMLALOCK_USER_ID: user_input.get(CONF_EMLALOCK_USER_ID, "").strip(),
                CONF_EMLALOCK_API_TOKEN: user_input.get(CONF_EMLALOCK_API_TOKEN, "").strip(),
            })
            return await self._async_next_service(self._selected_services.index("emlalock") + 1)
        return self.async_show_form(step_id="emlalock", data_schema=vol.Schema({
            vol.Optional(CONF_EMLALOCK_USER_ID, default=""): str,
            vol.Optional(CONF_EMLALOCK_API_TOKEN, default=""): str,
        }))

    async def async_step_chaster(self, user_input=None):
        if user_input is not None:
            self._service_data[CONF_CHASTER_API_TOKEN] = user_input.get(
                CONF_CHASTER_API_TOKEN, ""
            ).strip()
            return await self._async_next_service(self._selected_services.index("chaster") + 1)
        return self.async_show_form(step_id="chaster", data_schema=vol.Schema({
            vol.Optional(CONF_CHASTER_API_TOKEN, default=""): str,
        }))

    async def async_step_chastify(self, user_input=None):
        if user_input is not None:
            self._service_data[CONF_CHASTIFY_DEV_TOKEN] = user_input.get(
                CONF_CHASTIFY_DEV_TOKEN, ""
            ).strip()
            return await self._async_next_service(self._selected_services.index("chastify") + 1)
        return self.async_show_form(step_id="chastify", data_schema=vol.Schema({
            vol.Optional(CONF_CHASTIFY_DEV_TOKEN, default=""): str,
        }))

    @staticmethod
    @callback
    def async_get_options_flow(config_entry):
        return ChastityCalendarOptionsFlow(config_entry)


class ChastityCalendarOptionsFlow(config_entries.OptionsFlow):
    """Edit monthly events and selected service credentials."""

    def __init__(self, config_entry):
        self._config_entry = config_entry
        self._selected_services = []
        self._service_data = {}
        self._events = DEFAULT_EVENTS
        self._poll_minutes = 5

    async def async_step_init(self, user_input=None):
        current = {**self._config_entry.data, **self._config_entry.options}
        self._events = current.get(CONF_EVENTS, DEFAULT_EVENTS)
        self._poll_minutes = current.get(CONF_POLL_MINUTES, 5)
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
                self._events = parsed
                self._selected_services = [
                    service for service in SERVICE_ORDER
                    if service in user_input.get(CONF_SERVICES, [])
                ]
                self._service_data = {
                    CONF_EVENTS: parsed,
                    CONF_SERVICES: self._selected_services,
                    CONF_POLL_MINUTES: int(user_input[CONF_POLL_MINUTES]),
                }
                # Preserve credentials for services that remain selected until their
                # dedicated page is submitted, while dropping credentials for deselected services.
                for service, keys in {
                    "emlalock": (CONF_EMLALOCK_USER_ID, CONF_EMLALOCK_API_TOKEN),
                    "chaster": (CONF_CHASTER_API_TOKEN,),
                    "chastify": (CONF_CHASTIFY_DEV_TOKEN,),
                }.items():
                    if service in self._selected_services:
                        for key in keys:
                            self._service_data[key] = current.get(key, "")
                return await self._async_next_service(0)
            except (ValueError, TypeError, KeyError, json.JSONDecodeError):
                return self.async_show_form(
                    step_id="init",
                    data_schema=self._schema(current),
                    errors={"base": "invalid_options"},
                )
        return self.async_show_form(step_id="init", data_schema=self._schema(current))

    async def _async_next_service(self, index):
        if index >= len(self._selected_services):
            return self.async_create_entry(title="", data=self._service_data)
        service = self._selected_services[index]
        return await getattr(self, f"async_step_{service}")()

    async def async_step_emlalock(self, user_input=None):
        if user_input is not None:
            self._service_data[CONF_EMLALOCK_USER_ID] = user_input.get(CONF_EMLALOCK_USER_ID, "").strip()
            self._service_data[CONF_EMLALOCK_API_TOKEN] = user_input.get(CONF_EMLALOCK_API_TOKEN, "").strip()
            return await self._async_next_service(self._selected_services.index("emlalock") + 1)
        return self.async_show_form(step_id="emlalock", data_schema=vol.Schema({
            vol.Optional(CONF_EMLALOCK_USER_ID, default=self._service_data.get(CONF_EMLALOCK_USER_ID, "")): str,
            vol.Optional(CONF_EMLALOCK_API_TOKEN, default=self._service_data.get(CONF_EMLALOCK_API_TOKEN, "")): str,
        }))

    async def async_step_chaster(self, user_input=None):
        if user_input is not None:
            self._service_data[CONF_CHASTER_API_TOKEN] = user_input.get(CONF_CHASTER_API_TOKEN, "").strip()
            return await self._async_next_service(self._selected_services.index("chaster") + 1)
        return self.async_show_form(step_id="chaster", data_schema=vol.Schema({
            vol.Optional(CONF_CHASTER_API_TOKEN, default=self._service_data.get(CONF_CHASTER_API_TOKEN, "")): str,
        }))

    async def async_step_chastify(self, user_input=None):
        if user_input is not None:
            self._service_data[CONF_CHASTIFY_DEV_TOKEN] = user_input.get(CONF_CHASTIFY_DEV_TOKEN, "").strip()
            return await self._async_next_service(self._selected_services.index("chastify") + 1)
        return self.async_show_form(step_id="chastify", data_schema=vol.Schema({
            vol.Optional(CONF_CHASTIFY_DEV_TOKEN, default=self._service_data.get(CONF_CHASTIFY_DEV_TOKEN, "")): str,
        }))

    @staticmethod
    def _schema(values):
        events = values.get(CONF_EVENTS, DEFAULT_EVENTS)
        return vol.Schema({
            vol.Required(CONF_EVENTS, default=json.dumps(events, indent=2)): str,
            vol.Required(CONF_SERVICES, default=values.get(CONF_SERVICES, [])): cv.multi_select(SERVICE_OPTIONS),
            vol.Required(CONF_POLL_MINUTES, default=values.get(CONF_POLL_MINUTES, 5)): vol.All(int, vol.Range(min=1, max=60)),
        })
