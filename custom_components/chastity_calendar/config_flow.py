"""Config flow for Chastity Calendar."""
from __future__ import annotations

import json
import uuid
from urllib.parse import urlencode, urlparse

from aiohttp import web
from homeassistant.components import webhook

import voluptuous as vol
from homeassistant import config_entries
from homeassistant.core import callback
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers import selector

from .const import (
    CONF_CHASTER_API_TOKEN,
    CONF_CHASTIFY_DEV_TOKEN,
    CONF_EMLALOCK_API_TOKEN,
    CONF_EMLALOCK_USER_ID,
    CONF_EVENTS,
    CONF_POLL_MINUTES,
    CONF_OBEDIENCE_ENABLED,
    CONF_OBEDIENCE_EXTENSION_ID,
    CONF_OBEDIENCE_SECRET,
    CONF_OBEDIENCE_DAILY_HABIT_ID,
    CONF_OBEDIENCE_YEARLY_HABIT_ID,
    CONF_MONTHLY_NOTIFICATION_DESTINATION,
    CONF_MONTHLY_NOTIFICATION_TARGETS,
    NOTIFICATION_DESTINATIONS,
    CONF_SERVICES,
    SERVICE_OPTIONS,
    DEFAULT_EVENTS,
    DOMAIN,
)


async def _async_start_obedience_authorization(flow):
    """Open Obedience's official extension authorization page."""
    flow._obedience_extension_id = str(uuid.uuid4())
    flow._obedience_webhook_id = webhook.async_generate_id()

    async def handle_redirect(hass, webhook_id, request):
        """Receive credentials returned by Obedience."""
        params = request.query
        returned_id = params.get("id", "")
        secret = params.get("secret", "")
        user_id = params.get("uid", "")
        if returned_id != flow._obedience_extension_id or not secret or not user_id:
            return web.Response(
                status=400,
                text="Obedience authorization failed. Return to Home Assistant and try again.",
            )
        result = await hass.config_entries.flow.async_configure(
            flow.flow_id,
            user_input={"id": returned_id, "secret": secret, "uid": user_id},
        )
        webhook.async_unregister(hass, webhook_id)
        if result.get("type") != "external_step_done":
            return web.Response(
                status=400,
                text="Home Assistant could not finish Obedience authorization. Return to Home Assistant.",
            )
        return web.Response(
            text="<html><body><p>Obedience connected. You can close this tab and return to Home Assistant.</p><script>window.close()</script></body></html>",
            content_type="text/html",
        )

    webhook.async_register(
        flow.hass,
        DOMAIN,
        "Obedience authorization callback",
        flow._obedience_webhook_id,
        handle_redirect,
        allowed_methods=["GET"],
    )
    redirect_url = webhook.async_generate_url(
        flow.hass, flow._obedience_webhook_id, prefer_external=True
    )
    if urlparse(redirect_url).scheme != "https":
        webhook.async_unregister(flow.hass, flow._obedience_webhook_id)
        return flow.async_abort(reason="obedience_https_required")

    authorization_url = "https://app.obedienceapp.com/home/extension-request?" + urlencode({
        "id": flow._obedience_extension_id,
        "name": "Chastity Calendar",
        "redirect": redirect_url,
    })
    return flow.async_external_step(step_id="obedience", url=authorization_url)


SERVICE_ORDER = ("emlalock", "chaster", "chastify")


class ChastityCalendarConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle config flow."""

    VERSION = 1

    def __init__(self):
        self._selected_services = []
        self._service_data = {}
        self._configure_obedience = False

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
                CONF_OBEDIENCE_ENABLED: bool(user_input.get(CONF_OBEDIENCE_ENABLED, False)),
            }
            self._configure_obedience = self._service_data[CONF_OBEDIENCE_ENABLED]
            return await self._async_next_service(0)
        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema({
                vol.Required(CONF_SERVICES, default=[]): cv.multi_select(SERVICE_OPTIONS),
                vol.Optional(CONF_OBEDIENCE_ENABLED, default=False): bool,
            }),
        )

    async def _async_next_service(self, index):
        """Show a credentials page only for each selected service."""
        if index >= len(self._selected_services):
            if self._configure_obedience:
                return await self.async_step_obedience()
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

    async def async_step_obedience(self, user_input=None):
        """Complete the external Obedience authorization step."""
        if user_input is None:
            return await _async_start_obedience_authorization(self)
        if user_input.get("id") != self._obedience_extension_id:
            return self.async_abort(reason="obedience_authorization_failed")
        self._obedience_auth_result = user_input
        return self.async_external_step_done(next_step_id="obedience_settings")

    async def async_step_obedience_settings(self, user_input=None):
        """Choose the Obedience habits after authorizing the account."""
        if user_input is not None:
            self._service_data.update({
                CONF_OBEDIENCE_EXTENSION_ID: self._obedience_auth_result["id"],
                CONF_OBEDIENCE_SECRET: self._obedience_auth_result["secret"],
                CONF_OBEDIENCE_DAILY_HABIT_ID: user_input.get(CONF_OBEDIENCE_DAILY_HABIT_ID, "").strip(),
                CONF_OBEDIENCE_YEARLY_HABIT_ID: user_input.get(CONF_OBEDIENCE_YEARLY_HABIT_ID, "").strip(),
                "obedience_user_id": self._obedience_auth_result.get("uid", ""),
            })
            return self.async_create_entry(title="Chastity Calendar", data=self._service_data)
        return self.async_show_form(step_id="obedience_settings", data_schema=vol.Schema({
            vol.Optional(CONF_OBEDIENCE_DAILY_HABIT_ID, default=""): str,
            vol.Optional(CONF_OBEDIENCE_YEARLY_HABIT_ID, default=""): str,
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
        self._notification_destination = "home_assistant"
        self._notification_targets = []
        self._configure_obedience = False

    async def async_step_init(self, user_input=None):
        current = {**self._config_entry.data, **self._config_entry.options}
        self._events = current.get(CONF_EVENTS, DEFAULT_EVENTS)
        self._poll_minutes = current.get(CONF_POLL_MINUTES, 5)
        self._notification_destination = current.get(CONF_MONTHLY_NOTIFICATION_DESTINATION, "home_assistant")
        self._notification_targets = current.get(CONF_MONTHLY_NOTIFICATION_TARGETS, [])
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
                self._configure_obedience = bool(user_input.get(CONF_OBEDIENCE_ENABLED, False))
                self._service_data = {
                    CONF_EVENTS: parsed,
                    CONF_SERVICES: self._selected_services,
                    CONF_POLL_MINUTES: int(user_input[CONF_POLL_MINUTES]),
                    CONF_MONTHLY_NOTIFICATION_DESTINATION: user_input.get(CONF_MONTHLY_NOTIFICATION_DESTINATION, "home_assistant"),
                    CONF_MONTHLY_NOTIFICATION_TARGETS: user_input.get(CONF_MONTHLY_NOTIFICATION_TARGETS, []),
                    CONF_OBEDIENCE_ENABLED: self._configure_obedience,
                }
                for key in (CONF_OBEDIENCE_EXTENSION_ID, CONF_OBEDIENCE_SECRET, CONF_OBEDIENCE_DAILY_HABIT_ID, CONF_OBEDIENCE_YEARLY_HABIT_ID):
                    self._service_data[key] = current.get(key, "")
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
            if self._configure_obedience:
                return await self.async_step_obedience()
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

    async def async_step_obedience(self, user_input=None):
        """Complete external Obedience authorization for the options flow."""
        if user_input is None:
            return await _async_start_obedience_authorization(self)
        if user_input.get("id") != self._obedience_extension_id:
            return self.async_abort(reason="obedience_authorization_failed")
        self._obedience_auth_result = user_input
        return self.async_external_step_done(next_step_id="obedience_settings")

    async def async_step_obedience_settings(self, user_input=None):
        """Choose Obedience habits after authorization."""
        if user_input is not None:
            self._service_data.update({
                CONF_OBEDIENCE_EXTENSION_ID: self._obedience_auth_result["id"],
                CONF_OBEDIENCE_SECRET: self._obedience_auth_result["secret"],
                CONF_OBEDIENCE_DAILY_HABIT_ID: user_input.get(CONF_OBEDIENCE_DAILY_HABIT_ID, "").strip(),
                CONF_OBEDIENCE_YEARLY_HABIT_ID: user_input.get(CONF_OBEDIENCE_YEARLY_HABIT_ID, "").strip(),
                "obedience_user_id": self._obedience_auth_result.get("uid", ""),
            })
            return self.async_create_entry(title="", data=self._service_data)
        return self.async_show_form(step_id="obedience_settings", data_schema=vol.Schema({
            vol.Optional(CONF_OBEDIENCE_DAILY_HABIT_ID, default=self._service_data.get(CONF_OBEDIENCE_DAILY_HABIT_ID, "")): str,
            vol.Optional(CONF_OBEDIENCE_YEARLY_HABIT_ID, default=self._service_data.get(CONF_OBEDIENCE_YEARLY_HABIT_ID, "")): str,
        }))

    @staticmethod
    def _schema(values):
        events = values.get(CONF_EVENTS, DEFAULT_EVENTS)
        return vol.Schema({
            vol.Required(CONF_EVENTS, default=json.dumps(events, indent=2)): str,
            vol.Required(CONF_SERVICES, default=values.get(CONF_SERVICES, [])): cv.multi_select(SERVICE_OPTIONS),
            vol.Optional(CONF_OBEDIENCE_ENABLED, default=values.get(CONF_OBEDIENCE_ENABLED, bool(values.get(CONF_OBEDIENCE_EXTENSION_ID) and values.get(CONF_OBEDIENCE_SECRET)))): bool,
            vol.Required(CONF_POLL_MINUTES, default=values.get(CONF_POLL_MINUTES, 5)): vol.All(int, vol.Range(min=1, max=60)),
            vol.Required(CONF_MONTHLY_NOTIFICATION_DESTINATION, default=values.get(CONF_MONTHLY_NOTIFICATION_DESTINATION, "home_assistant")): vol.In(NOTIFICATION_DESTINATIONS),
            vol.Optional(CONF_MONTHLY_NOTIFICATION_TARGETS, default=values.get(CONF_MONTHLY_NOTIFICATION_TARGETS, [])): selector.EntitySelector(selector.EntitySelectorConfig(domain="notify", multiple=True)),
        })
