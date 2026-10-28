---
name: ai-bdr-pilot
description: Run a fair AI BDR vs human BDR pilot - split one Evaboot (Sales Navigator) export into two matched cohorts with whole companies on one side, tag both in HubSpot, hand the AI cohort to an AI BDR tool as a CSV, then score meetings and cost per meeting for each side every week and write a readout that calls no winner too early. Use when the user wants to compare an AI BDR or AI SDR with human reps, run a BDR pilot, or measure cost per meeting.
---

# AI BDR pilot

This skill runs inside a clone of https://github.com/evaboot-labs/ai-bdr-pilot: it uses the repo's `pilot.py`, `PILOT.md` and `docs/`. If `pilot.py` is not in the working directory, clone the repo and work from there.

`pilot.py` does the split, every HubSpot call and the arithmetic. You get the list, explain the balance, and write the weekly readout.

## Rules

- **One list, one start date.** Both cohorts come from the same export and start the same day. Never top up one side.
- **Whole companies on one side.** `pilot.py split` does it; never move a person by hand.
- **Never call a winner early.** Under `min_meetings` on either side, the readout says "too early". `pilot.py check` fails otherwise.
- Use only the numbers in `queue/score.json`. Never invent a reply rate, a trend or a reason.
- Never ask for or paste a key. The user writes `HUBSPOT_TOKEN` into `.env` (`docs/connect-your-agent.md`).

## Step 0: check the setup

1. Run `python3 pilot.py -h`. If `.env` misses the key, walk the user through `docs/connect-your-agent.md`.
2. Run `mkdir -p data queue`.
3. Read `PILOT.md`. If it says `status: EXAMPLE`, ask for the pilot name, the start date, the BDR's monthly cost and the share of their week on the pilot, the AI BDR tool's monthly cost and the review hours. Rewrite the block and set `status: yours`.
4. Run `python3 pilot.py setup`. If properties are missing, show the list and run `python3 pilot.py setup --apply` on a yes.

## Step 1: one list

The list comes from one Evaboot export of the user's ICP search. With the Evaboot MCP server (`.mcp.json`), build the search with `build_sn_search_from_prompt`, export it with `export_sn_search_or_list` (1 credit per lead), and save the finished export as `data/export.json`. Or ask the user for an Evaboot export JSON. Aim for at least 200 people with a safe email per side for a real pilot.

```bash
python3 pilot.py facts data/export.json > queue/leads.json
```

Only people with a safe email stay in: both sides must be able to reach them.

## Step 2: split

```bash
python3 pilot.py split queue/leads.json > queue/cohorts.json
```

Show the balance table. "companies on both sides" must be 0. If one size or seniority differs by more than 3, say so before going on.

## Step 3: push

```bash
python3 pilot.py push queue/cohorts.json
```

Show the dry run: people already in HubSpot are left out, because someone may already talk to them. On a yes, run it again with `--apply`. Then tell the user:

- Import `queue/ai-cohort.csv` into the AI BDR tool and start it on the `start` date.
- Give the human cohort (HubSpot filter `BDR pilot cohort = Human BDR`) to the BDR the same day.
- Log every meeting in HubSpot on the contact. Set `BDR pilot reply` to Positive or Negative when a person replies, on both sides.

## Step 4: every week

```bash
python3 pilot.py score > queue/score.json
```

Write `queue/readout.md`, under 200 words: the verdict first, then one line per cohort with people, meetings, positive replies, money spent and cost per meeting. Then:

```bash
python3 pilot.py check queue/score.json queue/readout.md
```

Fix every `FAIL` before you show it. To get the readout every Monday without an agent, set up the n8n version (`docs/n8n.md`).
