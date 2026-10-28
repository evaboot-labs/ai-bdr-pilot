# Agent instructions

This repo runs an AI BDR vs human BDR pilot. It splits one Evaboot export into two matched cohorts (whole companies on one side, the same mix of company sizes and seniorities), tags both in HubSpot, gives the AI cohort to the user's AI BDR tool as a CSV, and every week scores meetings and cost per meeting for each side. When the user asks to compare an AI BDR with human BDRs, run a BDR pilot, or measure cost per meeting:

1. Follow the skill in `skills/ai-bdr-pilot/SKILL.md` step by step.
2. Read `PILOT.md` for the pilot name, dates and costs. If it says `status: EXAMPLE`, ask the user for their numbers and update it.
3. Use `pilot.py` for every HubSpot call. It needs `HUBSPOT_TOKEN` in `.env`.
4. If the user is not connected yet, follow `docs/connect-your-agent.md` with them.
5. If the user wants the weekly readout in n8n, follow `docs/n8n.md` with them one step at a time: you cannot click inside n8n, so say exactly what to do and wait for their confirmation.

Never write to HubSpot before the user has read the `pilot.py push` dry run and said yes. Never call a winner before each side reaches `min_meetings`: `pilot.py check` enforces it. Never ask for or handle an API key: the user writes it into `.env`. Never commit `.env`, `data/` or `queue/`: they hold real people's data.
