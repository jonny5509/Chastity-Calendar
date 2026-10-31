"""Config flow for Chastity Calendar."""
from __future__ import annotations

import uuid
from urllib.parse import urlencode

from homeassistant.components.cloud import CloudNotAvailable, async_remote_ui_url

import voluptuous as vol
from homeassistant import config_entries
from homeassistant.core import callback
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers import selector

from .obedience_auth import async_register_views

from .const import (
    CONF_CHASTER_API_TOKEN,
    CONF_CHASTIFY_DEV_TOKEN,
    CONF_EMLALOCK_API_TOKEN,
    CONF_EMLALOCK_USER_ID,
    CONF_EVENTS,
    CONF_INSTANCE_NAME,
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
    """Start the same authorization flow as the standalone Obedience integration."""
    async_register_views(flow.hass)

    external_url = flow.hass.config.external_url
    if not external_url or not external_url.startswith("https://"):
        try:
            external_url = async_remote_ui_url(flow.hass)
        except CloudNotAvailable:
            external_url = None

    if not external_url or not external_url.startswith("https://"):
        return flow.async_abort(reason="obedience_https_required")

    extension_id = str(uuid.uuid4())
    domain_data = flow.hass.data.setdefault(DOMAIN, {})
    pending = domain_data.setdefault("obedience_pending", {})
    pending[extension_id] = {
        "flow_id": flow.flow_id,
        "manager": "options" if isinstance(flow, config_entries.OptionsFlow) else "flow",
    }
    callback_url = f"{external_url.rstrip('/')}/api/chastity_calendar/obedience/callback"
    authorization_url = "https://app.obedienceapp.com/home/extension-request?" + urlencode({
        "id": extension_id,
        "name": "Chastity Calendar",
        "redirect": callback_url,
    })
    flow._obedience_extension_id = extension_id
    return flow.async_external_step(step_id="obedience", url=authorization_url)


SERVICE_ORDER = ("emlalock", "chaster", "chastify")


class ChastityCalendarConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle config flow."""

    VERSION = 1

    def __init__(self):
        self._selected_services = []
        self._service_data = {}
        self._configure_obedience = False
        self._instance_name = "Chastity Calendar"

    async def async_step_user(self, user_input=None):
        """Select which services to configure."""
        if user_input is not None:
            self._instance_name = str(user_input.get(CONF_INSTANCE_NAME, "")).strip()
            if not self._instance_name:
                self._instance_name = "Chastity Calendar"
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
                vol.Required(CONF_INSTANCE_NAME, default="Chastity Calendar"): str,
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
                title=self._instance_name, data=self._service_data
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
                CONF_OBEDIENCE_DAILY_HABIT_ID: str(user_input.get(CONF_OBEDIENCE_DAILY_HABIT_ID) or "").strip(),
                CONF_OBEDIENCE_YEARLY_HABIT_ID: str(user_input.get(CONF_OBEDIENCE_YEARLY_HABIT_ID) or "").strip(),
                "obedience_user_id": self._obedience_auth_result.get("uid", ""),
            })
            return self.async_create_entry(title=self._instance_name, data=self._service_data)
        return self.async_show_form(step_id="obedience_settings", data_schema=vol.Schema({
            vol.Optional(CONF_OBEDIENCE_DAILY_HABIT_ID, default=""): str,
            vol.Optional(CONF_OBEDIENCE_YEARLY_HABIT_ID, default=""): str,
        }))

    @staticmethod
    @callback
    def async_get_options_flow(config_entry):
        return ChastityCalendarOptionsFlow(config_entry)


class ChastityCalendarOptionsFlow(config_entries.OptionsFlow):
    """Expose notification delivery preferences only after initial setup.

    Service selection, credentials, calendar themes, polling, points, and
    Obedience configuration are intentionally setup-only, matching the
    restricted configuration model used by Chastify HA.
    """

    def __init__(self, config_entry):
        self._config_entry = config_entry

    async def async_step_init(self, user_input=None):
        """Allow notification delivery changes without exposing core settings."""
        current = {**self._config_entry.data, **self._config_entry.options}

        if user_input is not None:
            # Preserve all previously stored options, including legacy values,
            # while only accepting the notification fields shown on this form.
            updated_options = {
                **self._config_entry.options,
                CONF_MONTHLY_NOTIFICATION_DESTINATION: user_input.get(
                    CONF_MONTHLY_NOTIFICATION_DESTINATION, "home_assistant"
                ),
                CONF_MONTHLY_NOTIFICATION_TARGETS: user_input.get(
                    CONF_MONTHLY_NOTIFICATION_TARGETS, []
                ),
            }
            return self.async_create_entry(title="", data=updated_options)

        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema({
                vol.Required(
                    CONF_MONTHLY_NOTIFICATION_DESTINATION,
                    default=current.get(
                        CONF_MONTHLY_NOTIFICATION_DESTINATION, "home_assistant"
                    ),
                ): vol.In(NOTIFICATION_DESTINATIONS),
                vol.Optional(
                    CONF_MONTHLY_NOTIFICATION_TARGETS,
                    default=current.get(CONF_MONTHLY_NOTIFICATION_TARGETS, []),
                ): selector.EntitySelector(
                    selector.EntitySelectorConfig(domain="notify", multiple=True)
                ),
            }),
        )
