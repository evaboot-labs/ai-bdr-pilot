# Your pilot

`pilot.py` reads the `key: value` lines below. Change them to your numbers, then set `status: yours`.

```text
status: EXAMPLE
pilot: uk-saas-q4
start: 2026-10-28
weeks: 6
currency: GBP
human_cost_per_month: 5500
human_share_on_pilot: 0.5
ai_cost_per_month: 900
ai_review_hours_per_week: 3
review_hourly_cost: 45
min_meetings: 10
```

| Key | What it means |
|---|---|
| `pilot` | The name written on every contact of this pilot (`bdr_pilot`). One name per pilot. |
| `start` | The first day both sides may contact their cohort. Meetings before it do not count. |
| `weeks` | How long the pilot runs. Six weeks covers a full sequence and the late replies. |
| `human_cost_per_month` | One BDR, fully loaded: salary, tax, tools, data and a share of the manager. |
| `human_share_on_pilot` | The part of that BDR's time on the human cohort. 0.5 = half their week. |
| `ai_cost_per_month` | The AI BDR tool, its sending domains and mailboxes, and its data. |
| `ai_review_hours_per_week` | The time a person spends checking the AI's emails and replies. It is never zero. |
| `review_hourly_cost` | The hourly cost of that person. |
| `min_meetings` | No winner is called before each side has this many meetings. Under 10, one good week decides the result. |

## The rules of a fair pilot

- **Same list, same week.** Both cohorts come from one Evaboot export and start on the same day.
- **Whole companies on one side.** Two colleagues never get two different BDRs.
- **Only new people.** Anyone already in your CRM is left out: someone may already talk to them.
- **One meeting definition.** A meeting is a HubSpot meeting linked to the contact, after `start`, not cancelled.
- **A positive reply is set by a person**, in `bdr_pilot_reply`, for both sides alike.
