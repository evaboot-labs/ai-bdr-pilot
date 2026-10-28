# Run the weekly readout in n8n

[`n8n/ai-bdr-pilot.json`](../n8n/ai-bdr-pilot.json) is the weekly score of `pilot.py` for n8n. Every Monday at 8 it counts each cohort's meetings in HubSpot, works out the cost per held meeting, asks Claude for a short readout and adds one row to an n8n Data table. The split and the push happen once: run them with `pilot.py`.

## What runs

1. **Every Monday at 8** and **Settings**: the same keys as `PILOT.md`.
2. **Pilot contacts** (HubSpot search): every contact with your `bdr_pilot` name, up to 200.
3. **Their meetings** and **Meeting details**: the meetings linked to each contact, with their date and outcome.
4. **Score**: meetings after `start`, booked (not cancelled) and held (outcome *Completed*), money spent so far, cost per held meeting, and "too early" under `min_meetings` held meetings.
5. **Weekly readout** (Claude) and **Check the readout**: the readout must quote the real numbers and call no winner too early. A failed check is written in the `check` column.
6. **Add to Pilot readouts**: one row a week in the Data table.

## Set it up

1. **Create the Data table** *Pilot readouts* (*Overview > Data tables*) with the columns `week_of`, `pilot`, `verdict`, `readout`, `check` (text) and `ai_people`, `ai_booked`, `ai_held`, `ai_cost_per_held_meeting`, `human_people`, `human_booked`, `human_held`, `human_cost_per_held_meeting` (number).
2. **Import** the JSON in n8n: *Workflows > Import from file*.
3. **Add two credentials:**
   - **HubSpot App Token** on the three HubSpot nodes: the key from `docs/connect-your-agent.md`.
   - **Anthropic** on the Claude node.
4. **Fill in Settings** with the values of your `PILOT.md`, and pick your table in **Add to Pilot readouts**.
5. **Test:** click **Execute workflow**, then open the Data table.
6. **Publish** the workflow so it runs every Monday.

## Good to know

- The workflow reads HubSpot only. It never changes a contact.
- Over 200 people in the pilot, run `pilot.py score` instead: it pages through every contact.
- HubSpot's search can take a minute to see a contact created a moment ago.

Back to the [README](../README.md).
