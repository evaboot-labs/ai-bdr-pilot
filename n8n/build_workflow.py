"""Builds n8n/ai-bdr-pilot.json. Run: python3 n8n/build_workflow.py

Every Monday at 8, the workflow reads the pilot's contacts from HubSpot, counts the meetings of each cohort
since the start (cancelled ones left out), works out the cost per meeting from your settings, asks Claude for
a short readout and adds one row to the "Pilot readouts" Data table. Same rules as pilot.py score and check.
The split and the push are one-off steps: run them with pilot.py.
"""
import json
import uuid
from pathlib import Path

ANTHROPIC_CRED = {"anthropicApi": {"id": "", "name": "Anthropic"}}
HUBSPOT_CRED = {"hubspotAppToken": {"id": "", "name": "HubSpot"}}
MODEL = "claude-sonnet-5-5"
SETTINGS = [("pilot", "uk-saas-q4"), ("start", "2026-10-28"), ("weeks", "6"), ("currency", "GBP"),
            ("human_cost_per_month", "5500"), ("human_share_on_pilot", "0.5"), ("ai_cost_per_month", "900"),
            ("ai_review_hours_per_week", "3"), ("review_hourly_cost", "45"), ("min_meetings", "10")]

nodes, connections = [], {}


def node(name, type_, version, params, pos, creds=None, **extra):
    n = {"parameters": params, "id": str(uuid.uuid4()), "name": name, "type": type_,
         "typeVersion": version, "position": pos, **extra}
    if creds:
        n["credentials"] = creds
    nodes.append(n)


def link(a, b, kind="main"):
    connections.setdefault(a, {}).setdefault(kind, [[]])[0].append({"node": b, "type": kind, "index": 0})


def hubspot(name, url, body_expr, pos):
    node(name, "n8n-nodes-base.httpRequest", 4.2, {
        "method": "POST", "url": url, "authentication": "predefinedCredentialType",
        "nodeCredentialType": "hubspotAppToken", "sendBody": True, "specifyBody": "json", "jsonBody": body_expr,
        "options": {}}, pos, HUBSPOT_CRED, executeOnce=True)


SCORE_JS = r"""
// Same as pilot.py score: meetings after the start that were not cancelled, cost per meeting per cohort.
const s = $('Settings').first().json;
const contacts = $('Pilot contacts').first().json.results || [];
const links = {};
for (const r of ($('Their meetings').first().json.results || [])) links[String(r.from.id)] = (r.to || []).map(t => String(t.toObjectId));
const good = new Set((($('Meeting details').first().json.results) || [])
  .filter(m => String(m.properties.hs_meeting_outcome || '').toUpperCase() !== 'CANCELED' && String(m.properties.hs_timestamp || '') >= s.start)
  .map(m => String(m.id)));
const weeksRun = Math.max(1, Math.floor((Date.now() - Date.parse(s.start)) / 6048e5) + 1);
const weeks = Math.min(weeksRun, Number(s.weeks));
const month = weeks / 4.33;
const cost = { human: Number(s.human_cost_per_month) * Number(s.human_share_on_pilot) * month,
  ai: Number(s.ai_cost_per_month) * month + Number(s.ai_review_hours_per_week) * Number(s.review_hourly_cost) * weeks };
const cohorts = {};
for (const side of ['ai', 'human']) {
  const rows = contacts.filter(c => c.properties.bdr_pilot_cohort === side);
  const met = rows.filter(c => (links[String(c.id)] || []).some(m => good.has(m))).length;
  cohorts[side] = { people: rows.length, positive_replies: rows.filter(c => c.properties.bdr_pilot_reply === 'positive').length,
    meetings: met, meetings_per_100: rows.length ? Math.round(1000 * met / rows.length) / 10 : 0,
    cost: Math.round(cost[side]), cost_per_meeting: met ? Math.round(cost[side] / met) : null };
}
const low = Object.keys(cohorts).filter(k => cohorts[k].meetings < Number(s.min_meetings));
const verdict = low.length ? 'too early' : (cohorts.ai.cost_per_meeting < cohorts.human.cost_per_meeting ? 'ai cheaper' : 'human cheaper');
return [{ json: { pilot: s.pilot, start: s.start, weeks_counted: weeks, currency: s.currency, min_meetings: Number(s.min_meetings), cohorts, verdict } }];
"""

CHECK_JS = r"""
// Same as pilot.py check: the readout quotes the real numbers and calls no winner before the minimum.
const sc = $('Score').first().json;
const text = String($json.output.readout || '');
const flat = text.replace(/,/g, '');
const problems = [];
for (const [side, v] of Object.entries(sc.cohorts)) {
  for (const key of ['people', 'meetings']) if (!new RegExp('\\b' + v[key] + '\\b').test(flat)) problems.push(`${side} ${key} missing`);
  if (v.cost_per_meeting && !flat.includes(String(v.cost_per_meeting))) problems.push(`${side} cost per meeting missing`);
}
if (sc.verdict === 'too early') {
  if (!/too early/i.test(text)) problems.push('must say too early');
  if (/\b(wins?|won|winner|beats?|outperform\w*)\b/i.test(text)) problems.push('calls a winner too early');
}
if (/\b(he|she|him|her|his|hers)\b/i.test(text)) problems.push('guesses a gender');
const a = sc.cohorts.ai, h = sc.cohorts.human;
return [{ json: { week_of: new Date().toISOString().slice(0, 10), pilot: sc.pilot, verdict: sc.verdict,
  ai_people: a.people, ai_meetings: a.meetings, ai_cost_per_meeting: a.cost_per_meeting ?? 0,
  human_people: h.people, human_meetings: h.meetings, human_cost_per_meeting: h.cost_per_meeting ?? 0,
  readout: text, check: problems.length ? 'FAIL: ' + problems.join('; ') : 'OK' } }];
"""

READOUT_SYSTEM = """You write the weekly readout of an AI BDR vs human BDR pilot for a sales leader. Use only the numbers in the JSON. Never invent a number, a reason or a trend.

Return {readout}: under 120 words, plain text.
- Line 1: the verdict. If the verdict is "too early", say "Too early to call" and how many meetings each side still needs; never say who wins or leads.
- Then one line per cohort: people, meetings, positive replies, money spent so far, and the cost per meeting when there is one, with the currency.
- Never guess anyone's gender."""

node("Every Monday at 8", "n8n-nodes-base.scheduleTrigger", 1.2, {"rule": {"interval": [
    {"field": "cronExpression", "expression": "0 8 * * 1"}]}}, [0, 0])
node("Settings", "n8n-nodes-base.set", 3.4, {"assignments": {"assignments": [
    {"id": str(uuid.uuid4()), "name": k, "type": "string", "value": v} for k, v in SETTINGS]},
    "options": {}}, [200, 0])
hubspot("Pilot contacts", "https://api.hubapi.com/crm/v3/objects/contacts/search",
        "={{ JSON.stringify({ limit: 200, properties: ['email', 'bdr_pilot_cohort', 'bdr_pilot_reply'], filterGroups: "
        "[{ filters: [{ propertyName: 'bdr_pilot', operator: 'EQ', value: $json.pilot }] }] }) }}", [400, 0])
hubspot("Their meetings", "https://api.hubapi.com/crm/v4/associations/contacts/meetings/batch/read",
        "={{ JSON.stringify({ inputs: ($json.results || []).map(c => ({ id: c.id })) }) }}", [600, 0])
hubspot("Meeting details", "https://api.hubapi.com/crm/v3/objects/meetings/batch/read",
        "={{ JSON.stringify({ properties: ['hs_timestamp', 'hs_meeting_outcome'], inputs: [...new Set(($json.results || [])"
        ".flatMap(r => (r.to || []).map(t => String(t.toObjectId))))].map(id => ({ id })).concat([{ id: '0' }]) }) }}",
        [800, 0])
nodes[-1]["parameters"]["options"] = {"response": {"response": {"neverError": True}}}
node("Score", "n8n-nodes-base.code", 2, {"jsCode": SCORE_JS}, [1000, 0])
node("Weekly readout", "@n8n/n8n-nodes-langchain.agent", 2.2, {
    "promptType": "define", "hasOutputParser": True, "text": "={{ JSON.stringify($json) }}",
    "options": {"systemMessage": READOUT_SYSTEM, "maxIterations": 3},
}, [1220, 0], retryOnFail=True, maxTries=3, waitBetweenTries=2000)
node("Claude", "@n8n/n8n-nodes-langchain.lmChatAnthropic", 1.3, {
    "model": {"__rl": True, "mode": "list", "value": MODEL, "cachedResultName": MODEL},
    "options": {"maxTokensToSample": 2000},
}, [1180, 220], ANTHROPIC_CRED)
node("Readout", "@n8n/n8n-nodes-langchain.outputParserStructured", 1.3, {
    "schemaType": "manual",
    "inputSchema": json.dumps({"type": "object", "required": ["readout"],
                               "properties": {"readout": {"type": "string"}}}, indent=2),
}, [1340, 220])
node("Check the readout", "n8n-nodes-base.code", 2, {"jsCode": CHECK_JS}, [1500, 0])
node("Add to Pilot readouts", "n8n-nodes-base.dataTable", 1, {
    "dataTableId": {"__rl": True, "mode": "name", "value": "Pilot readouts"},
    "columns": {"mappingMode": "autoMapInputData", "value": {}, "matchingColumns": [], "schema": []},
    "options": {},
}, [1720, 0])

for a, b in [("Every Monday at 8", "Settings"), ("Settings", "Pilot contacts"), ("Pilot contacts", "Their meetings"),
             ("Their meetings", "Meeting details"), ("Meeting details", "Score"), ("Score", "Weekly readout"),
             ("Weekly readout", "Check the readout"), ("Check the readout", "Add to Pilot readouts")]:
    link(a, b)
link("Claude", "Weekly readout", "ai_languageModel")
link("Readout", "Weekly readout", "ai_outputParser")

workflow = {"name": "AI BDR pilot readout (HubSpot + Claude)", "nodes": nodes, "connections": connections,
            "settings": {"executionOrder": "v1"}, "pinData": {}}
out = Path(__file__).with_name("ai-bdr-pilot.json")
out.write_text(json.dumps(workflow, indent=2, ensure_ascii=False) + "\n")
print(out, len(nodes), "nodes")
