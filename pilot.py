"""AI BDR vs human BDR pilot: one Evaboot list, two matched cohorts, one cost per meeting for each side.

    python3 pilot.py facts data/export.json > queue/leads.json
        one row per person with a safe email, from an Evaboot export
    python3 pilot.py split queue/leads.json > queue/cohorts.json
        whole companies go to one side, balanced by company size; prints the balance
    python3 pilot.py setup [--apply]
        creates the four HubSpot contact properties the pilot uses
    python3 pilot.py push queue/cohorts.json [--apply]
        tags both cohorts in HubSpot and writes queue/ai-cohort.csv for your AI BDR tool; dry run unless --apply
    python3 pilot.py score > queue/score.json
        replies and meetings per cohort from HubSpot, costs from PILOT.md, cost per meeting
    python3 pilot.py check queue/score.json queue/readout.md
        the readout quotes the real numbers and calls no winner before the minimum

Needs HUBSPOT_TOKEN in the environment or in .env. PILOT_FILE=other.md reads another settings file. Python 3.9+, no packages.
"""
import argparse
import csv
import hashlib
import json
import os
import re
import sys
import urllib.error
import urllib.request
from collections import Counter, defaultdict
from datetime import date, datetime, timezone

API = "https://api.hubapi.com"
SIZES = ["1-10", "11-50", "51-200", "201-500", "501-1000", "1001-5000", "5001-10000", "10001+"]
GENDERED = re.compile(r"\b(he|she|him|her|his|hers)\b", re.I)
PROPS = [
    {"name": "bdr_pilot", "label": "BDR pilot", "type": "string", "fieldType": "text"},
    {"name": "bdr_pilot_cohort", "label": "BDR pilot cohort", "type": "enumeration", "fieldType": "select",
     "options": [{"label": "AI BDR", "value": "ai"}, {"label": "Human BDR", "value": "human"}]},
    {"name": "bdr_pilot_start", "label": "BDR pilot start", "type": "date", "fieldType": "date"},
    {"name": "bdr_pilot_reply", "label": "BDR pilot reply", "type": "enumeration", "fieldType": "select",
     "options": [{"label": "Positive", "value": "positive"}, {"label": "Negative", "value": "negative"}]},
]


def env(name):
    if os.environ.get(name):
        return os.environ[name]
    if os.path.exists(".env"):
        m = re.search(rf"^{name}=(.*)$", open(".env").read(), re.M)
        if m and m.group(1).strip():
            return m.group(1).strip().strip("'\"")
    sys.exit(f"{name} is missing: add it to .env")


def call(method, path, body=None):
    req = urllib.request.Request(API + path, method=method, data=None if body is None else json.dumps(body).encode(),
                                 headers={"Authorization": f"Bearer {env('HUBSPOT_TOKEN')}",
                                          "Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            return r.status, json.loads(r.read() or b"{}")
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read() or b"{}")


def settings(path=None):
    path = path or os.environ.get("PILOT_FILE", "PILOT.md")
    """The `key: value` lines of PILOT.md's settings block."""
    s = dict(re.findall(r"^([a-z_]+):\s*(\S+)", open(path).read(), re.M))
    if s.get("status") == "EXAMPLE":
        print("PILOT.md still says status: EXAMPLE, the numbers are ours, not yours", file=sys.stderr)
    return s


def seniority(title):
    t = title.lower()
    for level, words in [("c-level", r"\b(chief|cro|cco|ceo|coo|founder|owner|president)\b"),
                         ("vp", r"\b(vp|vice president|svp|evp)\b"), ("head", r"\bhead\b"),
                         ("director", r"\bdirector\b")]:
        if re.search(words, t):
            return level
    return "other"


def facts(path):
    out, seen, dropped = [], set(), Counter()
    for p in json.load(open(path)).get("prospects") or []:
        lid = p.get("Linkedin URL Unique ID") or ""
        if not lid or lid in seen:
            continue
        seen.add(lid)
        if (p.get("Email Status") or "").lower() != "safe" or not p.get("Email"):
            dropped["no safe email"] += 1
            continue
        title = " ".join(str(p.get("Current Job") or "").split())[:120]
        out.append({"id": lid, "first_name": p.get("First Name") or "", "last_name": p.get("Last Name") or "",
                    "email": p["Email"].lower(), "title": title, "seniority": seniority(title),
                    "company": p.get("Company Name") or "", "domain": p.get("Company Domain") or "",
                    "company_id": p.get("Company Linkedin URL Unique ID") or (p.get("Company Name") or "").lower(),
                    "size": (p.get("Company Employee Range") or "unknown").replace(" to ", "-"),
                    "linkedin": p.get("Linkedin URL Public") or ""})
    print(f"{len(out)} people with a safe email, {sum(dropped.values())} left out (no safe email)", file=sys.stderr)
    return out


def split(leads, seed="pilot"):
    """Whole companies to one side, so two colleagues never get two different BDRs. Each company goes to the
    side that keeps the head count, the company sizes and the seniorities most even."""
    companies = defaultdict(list)
    for l in leads:
        companies[l["company_id"]].append(l)
    tally = {"ai": Counter(), "human": Counter()}

    def features(people):
        c = Counter({"people": len(people)})
        for l in people:
            c["size " + l["size"]] += 1
            c["seniority " + l["seniority"]] += 1
        return c

    def gap(ai, human):
        return sum((ai[k] - human[k]) ** 2 for k in set(ai) | set(human))

    cids = sorted(companies, key=lambda c: hashlib.sha1(f"{seed}{c}".encode()).hexdigest())
    cids.sort(key=lambda c: -len(companies[c]))  # big companies first, small ones even out the rest
    for cid in cids:
        f = features(companies[cid])
        to_ai = gap(tally["ai"] + f, tally["human"])
        to_human = gap(tally["ai"], tally["human"] + f)
        side = "ai" if to_ai < to_human or (to_ai == to_human and tally["ai"]["people"] <= tally["human"]["people"]) else "human"
        tally[side] += f
        for l in companies[cid]:
            l["cohort"] = side
    return leads


def balance(leads):
    rows = [("people", lambda l: True)] + [(f"size {s}", (lambda s: lambda l: l["size"] == s)(s))
                                           for s in SIZES if any(l["size"] == s for l in leads)]
    rows += [(f"seniority {s}", (lambda s: lambda l: l["seniority"] == s)(s))
             for s in ["c-level", "vp", "head", "director", "other"] if any(l["seniority"] == s for l in leads)]
    lines = [f"{'':22} {'AI':>4} {'Human':>6}"]
    for name, f in rows:
        lines.append(f"{name:22} {sum(f(l) and l['cohort'] == 'ai' for l in leads):>4} "
                     f"{sum(f(l) and l['cohort'] == 'human' for l in leads):>6}")
    both = {l["company_id"] for l in leads if l["cohort"] == "ai"} & {l["company_id"] for l in leads if l["cohort"] == "human"}
    lines.append(f"companies on both sides: {len(both)}")
    return "\n".join(lines)


def setup(apply):
    status, d = call("GET", "/crm/v3/properties/contacts?archived=false")
    have = {p["name"] for p in d.get("results", [])}
    todo = [p for p in PROPS if p["name"] not in have]
    print(f"{len(todo)} of {len(PROPS)} properties to create: {', '.join(p['name'] for p in todo) or 'none'}")
    for p in todo if apply else []:
        status, d = call("POST", "/crm/v3/properties/contacts", {**p, "groupName": "contactinformation"})
        print(p["name"], "created" if status == 201 else f"failed ({status}): {d.get('message')}")


def existing(emails):
    found = {}
    for i in range(0, len(emails), 100):
        status, d = call("POST", "/crm/v3/objects/contacts/search", {"limit": 100, "properties": ["email", "bdr_pilot"],
                         "filterGroups": [{"filters": [{"propertyName": "email", "operator": "IN", "values": emails[i:i + 100]}]}]})
        if status != 200:
            sys.exit(f"HubSpot search failed ({status}): {d.get('message')}")
        for r in d["results"]:
            found[(r["properties"].get("email") or "").lower()] = r
    return found


def push(path, apply):
    s = settings()
    leads = json.load(open(path))
    known = existing([l["email"] for l in leads])
    fresh = [l for l in leads if l["email"] not in known]
    print(f"{len(leads)} people: {len(fresh)} new to HubSpot, {len(known)} already in HubSpot and left out "
          "(someone may already talk to them)")
    with open("queue/ai-cohort.csv", "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["first_name", "last_name", "email", "title", "company", "website", "linkedin"])
        for l in fresh:
            if l["cohort"] == "ai":
                w.writerow([l["first_name"], l["last_name"], l["email"], l["title"], l["company"], l["domain"], l["linkedin"]])
    print(f"queue/ai-cohort.csv: {sum(l['cohort'] == 'ai' for l in fresh)} people for your AI BDR tool")
    if not apply:
        print(f"dry run: {len(fresh)} contacts to create in HubSpot. Add --apply to write them.")
        return
    made = 0
    for i in range(0, len(fresh), 100):
        inputs = [{"properties": {"firstname": l["first_name"], "lastname": l["last_name"], "email": l["email"],
                                  "jobtitle": l["title"], "company": l["company"], "website": l["domain"],
                                  "bdr_pilot": s["pilot"], "bdr_pilot_cohort": l["cohort"],
                                  "bdr_pilot_start": s["start"]}} for l in fresh[i:i + 100]]
        status, d = call("POST", "/crm/v3/objects/contacts/batch/create", {"inputs": inputs})
        if status not in (200, 201, 207):
            sys.exit(f"HubSpot create failed ({status}): {d.get('message')}")
        made += len(d.get("results", []))
    print(f"created {made} contacts tagged bdr_pilot={s['pilot']}")


def pilot_contacts(name):
    out, after = [], None
    while True:
        body = {"limit": 100, "properties": ["email", "bdr_pilot_cohort", "bdr_pilot_reply"],
                "filterGroups": [{"filters": [{"propertyName": "bdr_pilot", "operator": "EQ", "value": name}]}]}
        if after:
            body["after"] = after
        status, d = call("POST", "/crm/v3/objects/contacts/search", body)
        if status != 200:
            sys.exit(f"HubSpot search failed ({status}): {d.get('message')}")
        out += d["results"]
        after = (d.get("paging") or {}).get("next", {}).get("after")
        if not after:
            return out


def meetings(contact_ids, since):
    """Contacts with at least one meeting since the pilot start that was not cancelled."""
    links = {}
    for i in range(0, len(contact_ids), 100):
        status, d = call("POST", "/crm/v4/associations/contacts/meetings/batch/read",
                         {"inputs": [{"id": c} for c in contact_ids[i:i + 100]]})
        for r in d.get("results", []):
            links[r["from"]["id"]] = [t["toObjectId"] for t in r.get("to", [])]
    ids = sorted({str(m) for ms in links.values() for m in ms})
    good = set()
    for i in range(0, len(ids), 100):
        status, d = call("POST", "/crm/v3/objects/meetings/batch/read",
                         {"properties": ["hs_timestamp", "hs_meeting_outcome"], "inputs": [{"id": m} for m in ids[i:i + 100]]})
        for m in d.get("results", []):
            p = m["properties"]
            if (p.get("hs_meeting_outcome") or "").upper() != "CANCELED" and (p.get("hs_timestamp") or "") >= since:
                good.add(m["id"])
    return {c for c, ms in links.items() if any(str(m) in good for m in ms)}


def score():
    s = settings()
    contacts = pilot_contacts(s["pilot"])
    met = meetings([c["id"] for c in contacts], s["start"])
    weeks_run = max(1, (date.today() - date.fromisoformat(s["start"])).days // 7 + 1)
    weeks = min(weeks_run, int(s["weeks"]))
    month = weeks / 4.33
    cost = {"human": float(s["human_cost_per_month"]) * float(s["human_share_on_pilot"]) * month,
            "ai": float(s["ai_cost_per_month"]) * month
                  + float(s["ai_review_hours_per_week"]) * float(s["review_hourly_cost"]) * weeks}
    out = {"pilot": s["pilot"], "start": s["start"], "weeks_counted": weeks, "currency": s["currency"],
           "min_meetings": int(s["min_meetings"]), "cohorts": {}}
    for side in ("ai", "human"):
        rows = [c for c in contacts if c["properties"].get("bdr_pilot_cohort") == side]
        n_met = sum(c["id"] in met for c in rows)
        pos = sum(c["properties"].get("bdr_pilot_reply") == "positive" for c in rows)
        out["cohorts"][side] = {"people": len(rows), "positive_replies": pos, "meetings": n_met,
                                "meetings_per_100": round(100 * n_met / len(rows), 1) if rows else 0,
                                "cost": round(cost[side]), "cost_per_meeting": round(cost[side] / n_met) if n_met else None}
    low = [k for k, v in out["cohorts"].items() if v["meetings"] < out["min_meetings"]]
    if low:
        out["verdict"] = "too early"
        out["why"] = f"{' and '.join(low)} below {out['min_meetings']} meetings"
    else:
        a, h = out["cohorts"]["ai"]["cost_per_meeting"], out["cohorts"]["human"]["cost_per_meeting"]
        out["verdict"] = "ai cheaper" if a < h else "human cheaper"
    print(f"{s['pilot']}, week {weeks}: AI {out['cohorts']['ai']['meetings']} meetings, human "
          f"{out['cohorts']['human']['meetings']} meetings, verdict: {out['verdict']}", file=sys.stderr)
    return out


def check(score_path, readout_path):
    sc, text = json.load(open(score_path)), open(readout_path).read()
    flat = text.replace(",", "")
    problems = []
    for side, v in sc["cohorts"].items():
        for key in ("people", "meetings"):
            if not re.search(rf"\b{v[key]}\b", flat):
                problems.append(f"{side} {key} ({v[key]}) is not in the readout")
        if v["cost_per_meeting"] and str(v["cost_per_meeting"]) not in flat:
            problems.append(f"{side} cost per meeting ({v['cost_per_meeting']}) is not in the readout")
    if sc["verdict"] == "too early":
        if "too early" not in text.lower():
            problems.append("the score says too early: the readout must say so")
        if re.search(r"\b(wins?|won|winner|beats?|outperform\w*)\b", text, re.I):
            problems.append("the readout calls a winner before the minimum number of meetings")
    if GENDERED.search(text):
        problems.append("the readout guesses a gender: use names, they or the role")
    if len(text.split()) > 200:
        problems.append("the readout is over 200 words")
    return problems


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("facts").add_argument("export")
    sp = sub.add_parser("split")
    sp.add_argument("leads")
    sp.add_argument("--seed", default="pilot")
    sub.add_parser("setup").add_argument("--apply", action="store_true")
    pp = sub.add_parser("push")
    pp.add_argument("cohorts")
    pp.add_argument("--apply", action="store_true")
    sub.add_parser("score")
    cp = sub.add_parser("check")
    cp.add_argument("score")
    cp.add_argument("readout")
    a = ap.parse_args()
    if a.cmd == "facts":
        json.dump(facts(a.export), sys.stdout, indent=1, ensure_ascii=False); print()
    elif a.cmd == "split":
        leads = split(json.load(open(a.leads)), a.seed)
        print(balance(leads), file=sys.stderr)
        json.dump(leads, sys.stdout, indent=1, ensure_ascii=False); print()
    elif a.cmd == "setup":
        setup(a.apply)
    elif a.cmd == "push":
        push(a.cohorts, a.apply)
    elif a.cmd == "score":
        json.dump(score(), sys.stdout, indent=1); print()
    else:
        problems = check(a.score, a.readout)
        for p in problems:
            print("FAIL", p)
        print("OK" if not problems else f"{len(problems)} problem(s)")
        sys.exit(1 if problems else 0)


if __name__ == "__main__":
    main()
