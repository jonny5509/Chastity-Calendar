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
        """Validate authorization response and resume the correct flow."""
        hass = request.app["hass"]
        extension_id = request.query.get("id", "")
        secret = request.query.get("secret", "")
        user_id = request.query.get("uid", "")
        pending = hass.data.get(DOMAIN, {}).get("obedience_pending", {})
        flow_id = pending.get(extension_id)

        if not flow_id or not extension_id or not secret or not user_id:
            return web.Response(
                status=400,
                text="Invalid Obedience authorization response. Return to Home Assistant and try again.",
            )

        user_input = {"id": extension_id, "secret": secret, "uid": user_id}
        result = None
        errors = []

        # Initial setup is a config flow; reconnecting from the integration's
        # options page is an options flow. Home Assistant manages these separately.
        for manager_name in ("flow", "options"):
            manager = getattr(hass.config_entries, manager_name, None)
            if manager is None:
                continue
            try:
                result = await manager.async_configure(flow_id, user_input)
                break
            except Exception as err:
                errors.append(f"{manager_name} flow: {err}")

        if result is None:
            pending.pop(extension_id, None)
            detail = "; ".join(errors) or "No compatible flow manager was available."
            return web.Response(
                status=500,
                text=f"Home Assistant could not complete Obedience authorization: {detail}",
            )

        result_type = result.get("type")
        expected_type = FlowResultType.EXTERNAL_STEP_DONE
        if result_type not in (
            expected_type,
            expected_type.value,
            "external_done",
        ):
            pending.pop(extension_id, None)
            return web.Response(
                status=500,
                text=f"Unexpected authorization flow result: {result_type}",
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
