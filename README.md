# Chastity Calendar for Home Assistant

A Home Assistant custom integration with monthly theme events and optional daily session-history tracking for EmlaLock, Chastify, and Chaster.

## Features
- Native Home Assistant calendar entity for dashboards and automations.
- Choose none, one, two, or all three services during setup. A separate credentials page is shown only for each selected service; credentials can be left blank and added later.
- Adds one all-day calendar event per date with a single emoji, even when two or all three services have overlapping sessions.
- Creates three Home Assistant service-status binary sensors (EmlaLock, Chaster, and Chastify) plus an Obedience authorization status sensor. Each service sensor reports on/off after a successful API check and is unavailable until that service is selected, configured, and checked.
- Saves history in Home Assistant's local storage. Existing records are append-only and remain after a session ends, a token is removed, or Home Assistant restarts.
- API polling interval configurable from 1 to 60 minutes (default 5).
- Editable monthly theme list.
- Monthly theme reminder on the first day of each month, using a message such as “Are you ready for No Nut November?”
- Choose a Home Assistant persistent notification, one or more phone notification targets, or both.
- Optional daily completion points: 100 points per completed date and a one-time 1,095-point bonus after 365 completed dates.

## Install with HACS
1. In HACS, open **Integrations** → menu → **Custom repositories**.
2. Add `https://github.com/jonny5509/Chastity-Calendar` and choose category **Integration**.
3. Download **Chastity Calendar** and restart Home Assistant.
4. Go to **Settings → Devices & services → Add integration** and search for **Chastity Calendar**.

## Configure service tracking
During initial setup, select none, one, or multiple services to track. Home Assistant then shows a separate configuration page for each selected service only. You can change the selection later from the integration's **Configure** page; the configuration flow again shows credential pages only for the selected services. Enter credentials for each selected service; all services are optional:
- **EmlaLock:** user ID and API key.
- **Chaster:** Developer Token for the Chaster Public API. It is sent as a Bearer token.
- **Chastify:** user-wide Developer API key with the `locks:read` scope. It is sent as a Bearer token.

Internet access: yes — Home Assistant needs outbound internet access to call the selected services' APIs and poll session status. The calendar entity and saved history are stored locally in Home Assistant, but live service tracking and API-based historical backfill will not work while Home Assistant cannot reach those services. Credentials are stored in the Home Assistant config entry, sent only to the respective service, and are not written to the repository or included in logs. Never share your tokens. If a token is revoked or a service is unavailable, already-saved calendar history is retained. Polling detects sessions while the integration is running; historical days before setup can only be recovered if an API exposes them.

## Set up each service

Create or enable the relevant API credentials in each provider account before entering them in Home Assistant. Website menu names can change, so if a label has moved, check the provider's current account or developer documentation. Chastity Calendar only reads session status; it does not create, unlock, or change sessions.

### EmlaLock

1. Sign in to your EmlaLock account.
2. Find the account/API settings that provide your **user ID** and **API key**. Use your API key, not your account password.
3. During Chastity Calendar setup, select **EmlaLock**. On its dedicated credentials page, enter both the user ID and API key.
4. Submit the flow. If the EmlaLock sensor remains unavailable, check Home Assistant logs and confirm the credentials are active.

### Chaster

1. Sign in to Chaster and open its developer/API area.
2. Create or copy a **Developer Token** with permission to read your session/lock data.
3. Select **Chaster** in Chastity Calendar and paste the token into its dedicated credentials page. The integration sends this token as a Bearer token.
4. Keep the token private. If access is denied, check that it is active and has the required read access.

### Chastify

1. Sign in to Chastify and open its developer/API settings.
2. Create or copy your **user-wide Developer API key** and ensure it includes the `locks:read` scope.
3. Select **Chastify** in the Chastity Calendar setup flow and paste the key into its dedicated credentials page.
4. If API checks fail, verify that the key belongs to your user account, has the required scope, and has not been revoked.

### Obedience

1. During initial setup, tick **Configure Obedience habit syncing**. For an existing integration, open **Settings → Devices & services → Chastity Calendar → Configure**, enable **Obedience habit syncing**, and submit. The next page is the separate Obedience setup page.
2. Choose **Open external website**. Home Assistant opens Obedience's official authorization page.
3. Sign in to Obedience and approve the extension request. Obedience redirects back to Home Assistant, which saves the extension credentials automatically. You never enter your Obedience password into Home Assistant or copy the extension secret manually.
4. Optionally enter the ID of an eligible daily-completion habit and/or a 365-day milestone habit. The integration increments each configured habit when the relevant milestone is reached; configure the habit rewards in Obedience itself.
5. This requires an HTTPS Home Assistant URL configured in Home Assistant, or Home Assistant Cloud Remote UI enabled. Leave habit IDs blank if you only want local Home Assistant points, or disable Obedience syncing to stop API updates.

For every service, enter credentials only into that service's matching field. Do not include API keys, tokens, or extension secrets in screenshots, issue reports, or logs. If a provider changes its API or credential flow, follow that provider's latest developer documentation.

## Monthly themes and reminders
The monthly event list is editable as JSON. Each item needs a month number and title; description is optional. Months use numbers 1–12. Monthly events are all-day and end at the first day of the following month (exclusive).

The integration can send a reminder at the start of each month, using that month's configured theme title (for example, “Are you ready for No Nut November?”). In **Settings → Devices & services → Chastity Calendar → Configure**, choose a Home Assistant persistent notification, phone notification(s), or both. For phone notifications, select one or more `notify` entities, such as the entities provided by the Home Assistant Companion App. The reminder is sent once per month and the last-sent month is stored locally.

## Daily completion points and optional Obedience sync

The integration automatically awards 100 points at the most recently recorded session start time each day, using Home Assistant's local time. When a monitored session is detected changing from active to inactive, it also checks dates from that session's recorded start through the end date and awards any missing dates. Each date is counted only once, so scheduled awards and catch-up cannot double-count. This catch-up requires the integration to observe the active-to-inactive transition and have a recognized session start date.

The `sensor.chastity_calendar_completion_points` sensor reports the total points and completion details in Home Assistant and updates when points change. The yearly bonus is awarded after 365 completed dates in total (not necessarily consecutive).

You can still call the `chastity_calendar.mark_day_complete` Home Assistant service manually. The optional `date` field accepts a date such as `2026-10-15`; if omitted, the current Home Assistant local date is used.

When Obedience syncing is enabled and a daily habit ID is configured, each completed date increments that Obedience habit once. An optional yearly habit is incremented for the 365-day milestone. The integration updates the configured Obedience habits; it does not directly write to an account-wide Obedience points balance. Configure the rewards for those habits in Obedience itself.

Obedience is optional and has its own setup page. During first-time setup, enable **Configure Obedience habit syncing** to open that page. Later, open **Settings → Devices & services → Chastity Calendar → Configure**, enable Obedience syncing, and submit to open the separate page. Enable Obedience syncing in Home Assistant and choose **Open external website**. Sign in on Obedience's official site and approve the extension request; the browser redirects back to Home Assistant and the extension credentials are saved automatically. Home Assistant never asks for your Obedience account password. This requires a publicly reachable HTTPS Home Assistant URL (for example, a configured HTTPS external URL or reverse proxy). Create or choose eligible habits and copy their IDs: one for daily completion and optionally one for the 365-day milestone. Set the rewards on those habits in Obedience itself. Home Assistant's local tracker awards 100 points per completed date and a one-time 1,095-point bonus after 365 completed dates; the integration increments the configured Obedience habits rather than directly writing a points balance. Habits requiring photo proof or habits your account cannot edit may be rejected. You can leave either habit ID blank, or disable Obedience syncing, to keep points local to Home Assistant.

Example service call:

```yaml
action: chastity_calendar.mark_day_complete
data:
  date: "2026-10-15"
```

## Notes
API response formats and scopes can change. Check Home Assistant logs if a service token is rejected. The integration does not control locks or change session state; it only reads session status and stores calendar history.
