# Chastity Calendar for Home Assistant

A Home Assistant custom integration with monthly theme events and optional daily session-history tracking for EmlaLock, Chastify, and Chaster.

## Features
- Native Home Assistant calendar entity for dashboards and automations.
- Choose none, one, two, or all three services during setup. A separate credentials page is shown only for each selected service; credentials can be left blank and added later.
- Adds one all-day calendar event per date with a single emoji, even when two or all three services have overlapping sessions.
- Creates three Home Assistant binary sensors: EmlaLock active session, Chaster active session, and Chastify active session. Each sensor reports on/off after a successful API check and is unavailable until that service is selected, configured, and checked.
- Saves history in Home Assistant's local storage. Existing records are append-only and remain after a session ends, a token is removed, or Home Assistant restarts.
- API polling interval configurable from 1 to 60 minutes (default 5).
- Editable monthly theme list.
- Monthly theme reminder on the first day of each month, using a message such as “Are you ready for No Nut November?”
- Choose a Home Assistant persistent notification, one or more phone notification targets, or both.

## Install with HACS
1. In HACS, open **Integrations** → menu → **Custom repositories**.
2. Add `https://github.com/jonny5509/calendar` and choose category **Integration**.
3. Download **Chastity Calendar** and restart Home Assistant.
4. Go to **Settings → Devices & services → Add integration** and search for **Chastity Calendar**.

## Configure service tracking
During initial setup, select none, one, or multiple services to track. Home Assistant then shows a separate configuration page for each selected service only. You can change the selection later from the integration's **Configure** page; the configuration flow again shows credential pages only for the selected services. Enter credentials for each selected service; all services are optional:
- **EmlaLock:** user ID and API key.
- **Chaster:** Developer Token for the Chaster Public API. It is sent as a Bearer token.
- **Chastify:** user-wide Developer API key with the `locks:read` scope. It is sent as a Bearer token.

Internet access: yes — Home Assistant needs outbound internet access to call the selected services' APIs and poll session status. The calendar entity and saved history are stored locally in Home Assistant, but live service tracking and API-based historical backfill will not work while Home Assistant cannot reach those services. Credentials are stored in the Home Assistant config entry, sent only to the respective service, and are not written to the repository or included in logs. Never share your tokens. If a token is revoked or a service is unavailable, already-saved calendar history is retained. Polling detects sessions while the integration is running; historical days before setup can only be recovered if an API exposes them.

## Monthly themes and reminders
The monthly event list is editable as JSON. Each item needs a month number and title; description is optional. Months use numbers 1–12. Monthly events are all-day and end at the first day of the following month (exclusive).

The integration can send a reminder at the start of each month, using that month's configured theme title (for example, “Are you ready for No Nut November?”). In **Settings → Devices & services → Chastity Calendar → Configure**, choose a Home Assistant persistent notification, phone notification(s), or both. For phone notifications, select one or more `notify` entities, such as the entities provided by the Home Assistant Companion App. The reminder is sent once per month and the last-sent month is stored locally.

## Notes
API response formats and scopes can change. Check Home Assistant logs if a service token is rejected. The integration does not control locks or change session state; it only reads session status and stores calendar history.
