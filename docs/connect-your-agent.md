# Connect your agent by hand

The prompt in the README does all of this for you. These are the same steps, for when you want to do them yourself.

1. **Create your Evaboot account** at [dash.evaboot.com](https://dash.evaboot.com/accounts/signup/?last_click_origin=ai-bdr-pilot-repo), with the [Chrome extension](https://dash.evaboot.com/install/) and a Sales Navigator seat. You need it for the list, once.
2. **Get the repo:**
   ```bash
   git clone https://github.com/evaboot-labs/ai-bdr-pilot.git
   cd ai-bdr-pilot
   ```
3. **Add your HubSpot key.** Create a private app or a service key with the scopes `crm.objects.contacts.read`, `crm.objects.contacts.write`, `crm.schemas.contacts.write` and `crm.objects.meetings.read` (shown as *Sales email read* on some accounts). Then:
   ```bash
   cp .env.example .env          # paste the key
   ```
4. **Create the four HubSpot properties** the pilot uses, once: `python3 pilot.py setup --apply`.
5. **Write your numbers** in [`PILOT.md`](../PILOT.md), or let your agent ask you.
6. **Check** (Python 3.9+, no packages to install): `python3 pilot.py -h` lists the commands.

Then ask your agent: **"Run an AI BDR vs human BDR pilot on my Evaboot export."**

The repo also ships `.mcp.json` for the Evaboot MCP server (`https://mcp.evaboot.com/mcp`, it reads `EVABOOT_API_KEY`), so your agent can build the Sales Navigator search and export the list in the same session. `pilot.py` does not need it.

Back to the [README](../README.md).
