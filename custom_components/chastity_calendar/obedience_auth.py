"""Obedience authorization callback for Chastity Calendar."""
from __future__ import annotations

from aiohttp import web
from homeassistant.components.http import HomeAssistantView
from homeassistant.data_entry_flow import FlowResultType

from .const import DOMAIN


def async_register_views(hass) -> None:
    """Register the callback view once."""
    key = f"{DOMAIN}_obedience_auth_view_registered"
    if hass.data.get(key):
        return
    hass.http.register_view(ObedienceAuthorizationCallbackView)
    hass.data[key] = True


class ObedienceAuthorizationCallbackView(HomeAssistantView):
    """Receive the redirect from Obedience after user approval."""

    url = "/api/chastity_calendar/obedience/callback"
    name = "api:chastity_calendar:obedience_callback"
    requires_auth = False

    async def get(self, request: web.Request) -> web.Response:
        """Validate authorization response and resume the config flow."""
        hass = request.app["hass"]
        extension_id = request.query.get("id", "")
        secret = request.query.get("secret", "")
        user_id = request.query.get("uid", "")
        domain_data = hass.data.get(DOMAIN, {})
        pending = domain_data.get("obedience_pending", {})
        flow_id = pending.get(extension_id)

        if not flow_id or not extension_id or not secret or not user_id:
            return web.Response(
                status=400,
                text="Invalid Obedience authorization response. Return to Home Assistant and try again.",
            )

        try:
            result = await hass.config_entries.flow.async_configure(
                flow_id,
                user_input={"id": extension_id, "secret": secret, "uid": user_id},
            )
        except Exception:
            pending.pop(extension_id, None)
            return web.Response(
                status=500,
                text="Home Assistant could not complete Obedience authorization. Return to Home Assistant and try again.",
            )

        result_type = result.get("type")
        if result_type not in (
            FlowResultType.EXTERNAL_STEP_DONE,
            FlowResultType.EXTERNAL_STEP_DONE.value,
            "external_done",
        ):
            pending.pop(extension_id, None)
            return web.Response(
                status=500,
                text="Unexpected result completing Obedience authorization. Return to Home Assistant.",
            )

        pending.pop(extension_id, None)
        return web.Response(
            content_type="text/html",
            text=(
                "<!doctype html><html><head><title>Obedience connected</title></head>"
                "<body><p>Obedience connected. You can close this window.</p>"
                "<script>window.close()</script></body></html>"
            ),
        )
