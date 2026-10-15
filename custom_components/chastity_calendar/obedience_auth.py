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
        flow_record = pending.get(extension_id)
        # New records remember which manager owns the flow. Keep accepting the
        # legacy flow-id string while an authorization is already in progress.
        if isinstance(flow_record, dict):
            flow_id = flow_record.get("flow_id")
            preferred_manager = flow_record.get("manager", "flow")
        else:
            flow_id = flow_record
            preferred_manager = "flow"

        if not flow_id or not extension_id or not secret or not user_id:
            return web.Response(
                status=400,
                text="Invalid Obedience authorization response. Return to Home Assistant and try again.",
            )

        user_input = {"id": extension_id, "secret": secret, "uid": user_id}
        result = None
        errors = []
        unexpected_types = []
        expected_type = FlowResultType.EXTERNAL_STEP_DONE

        # Initial setup and options flows have separate managers. Try the owner
        # first, then the other manager for compatibility with older pending flows.
        manager_order = (preferred_manager, "options" if preferred_manager == "flow" else "flow")
        for manager_name in manager_order:
            manager = getattr(hass.config_entries, manager_name, None)
            if manager is None:
                errors.append(f"{manager_name} flow manager is unavailable")
                continue
            try:
                candidate = await manager.async_configure(flow_id, user_input)
            except Exception as err:
                errors.append(f"{manager_name} flow: {err}")
                continue
            result_type = candidate.get("type")
            if result_type in (expected_type, expected_type.value, "external_done"):
                result = candidate
                break
            unexpected_types.append(f"{manager_name} flow returned {result_type}")

        if result is None:
            pending.pop(extension_id, None)
            detail = "; ".join(errors + unexpected_types) or "No compatible flow manager was available."
            return web.Response(
                status=500,
                text=f"Home Assistant could not complete Obedience authorization: {detail}",
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
