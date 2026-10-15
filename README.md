# Chastity Calendar for Home Assistant

A Home Assistant custom integration with monthly theme events and optional daily session-history tracking for EmlaLock, Chastify, and Chaster.

## Features
- Native Home Assistant calendar entity for dashboards and automations.
- Choose none, one, two, or all three services during setup; API credentials are optional and can be entered later.
- Adds one all-day calendar event for each date a configured service reports an active session, decorated with a randomly selected 👑 💅 👠 💄 ✨ or 🎀 emoji.
- Saves history in Home Assistant's local storage. Existing records are append-only and remain after a session ends, a token is removed, or Home Assistant restarts.
- API polling interval configurable from 1 to 60 minutes (default 5).
- Editable monthly theme list.

## Install with HACS
1. In HACS, open **Integrations** → menu → **Custom repositories**.
2. Add `https://github.com/jonny5509/calendar` and choose category **Integration**.
3. Download **Chastity Calendar** and restart Home Assistant.
4. Go to **Settings → Devices & services → Add integration** and search for **Chastity Calendar**.

## Configure service tracking
During initial setup, select none, one, or multiple services to track. You can change this selection later from the integration's **Configure** page. Enter credentials for each selected service; all services are optional:
- **EmlaLock:** user ID and API key.
- **Chastify:** user-wide Developer API token with `locks:read` scope.
- **Chaster:** Public API developer/access token with permission to read locks.

Internet access: yes — Home Assistant needs outbound internet access to call the selected services' APIs and poll session status. The calendar entity and saved history are stored locally in Home Assistant, but live service tracking and API-based historical backfill will not work while Home Assistant cannot reach those services. Credentials are stored in the Home Assistant config entry, sent only to the respective service, and are not written to the repository or included in logs. Never share your tokens. If a token is revoked or a service is unavailable, already-saved calendar history is retained. Polling detects sessions while the integration is running; historical days before setup can only be recovered if an API exposes them.

## Monthly themes
The monthly event list is editable as JSON. Each item needs a month number and title; description is optional. Months use numbers 1–12. Monthly events are all-day and end at the first day of the following month (exclusive).

## Notes
API response formats and scopes can change. Check Home Assistant logs if a service token is rejected. The integration does not control locks or change session state; it only reads session status and stores calendar history.
