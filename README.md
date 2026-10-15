# Chastity Calendar for Home Assistant

A local Home Assistant custom integration that exposes a calendar of monthly chastity and abstinence challenge themes. It works offline and does not send calendar data anywhere.

## Features

- Creates `calendar.chastity_calendar_monthly_themes`
- Month-long all-day events, including Locktober in October
- Includes community-style names for all 12 months
- Uses Home Assistant's native calendar entity for dashboards and automations
- No external API, account, or additional Python dependency

The names are informal community-style suggestions, not an official or universally agreed calendar. Some names vary between communities; you can customize them.

## Install with HACS

1. In HACS, open **Integrations** → menu → **Custom repositories**.
2. Add `https://github.com/jonny5509/calendar` and choose category **Integration**.
3. Download **Chastity Calendar** and restart Home Assistant.
4. Go to **Settings → Devices & services → Add integration** and search for **Chastity Calendar**.

## Customize monthly events

Open the integration's **Configure** option. The monthly event list is editable as JSON. Each item needs a month number and title; description is optional.

```json
[
  {"month": 10, "title": "Locktober", "description": "Optional, consensual month-long challenge."},
  {"month": 11, "title": "No Nut November", "description": "Optional abstinence challenge."},
  {"month": 12, "title": "My December Theme", "description": "Your own description."}
]
```

Months use numbers 1–12. Events are all-day and end at the first day of the following month (the end date is exclusive).

## Example automation

```yaml
automation:
  - alias: "Notify when Locktober begins"
    triggers:
      - trigger: calendar
        event: start
        entity_id: calendar.chastity_calendar_monthly_themes
    conditions:
      - condition: template
        value_template: "{{ trigger.calendar_event.summary == 'Locktober' }}"
    actions:
      - action: persistent_notification.create
        data:
          title: "Monthly theme"
          message: "Locktober starts today. Keep all activities consensual and safe."
```

## Notes

- This is a starter integration and has not been validated against every Home Assistant release. Test it before relying on it for important automations.
- Participation in any challenge is optional; agree boundaries in advance and prioritize comfort and safety.
- Contributions and issue reports are welcome.
