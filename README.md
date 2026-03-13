# PM Weekly Newsletter Generator

Automated weekly newsletter generator for Product Managers. Pulls data from Slack, Jira, and Google Drive, then synthesizes it into a formatted newsletter with executive summary, sprint status, blockers, key decisions, and action items.

Output as **Slack Canvas**, **Google Doc**, or **local Markdown**.

## Newsletter Sections

1. **Executive Summary** — What shipped, key decisions, top risks, what needs attention
2. **Blockers & Risks** — Table of stuck stories, high-priority issues, dependencies at risk with suggested actions
3. **Key Decisions & Outcomes** — Decisions made in Slack with channel and date
4. **Sprint Status** — Health numbers grouped by work stream and component
5. **Conversations & Threads** — Key Slack thread summaries
6. **Pending — Needs Your Response** — Unanswered questions with suggested starting points
7. **Document Activity** — Recently modified Google Drive files (optional)
8. **Action Items & Follow-Ups** — Prioritized checklist

## Architecture

```
pm-newsletter/
├── generate.py                    # Main orchestrator — runs all collectors, synthesizes newsletter
├── formatter.py                   # Google Docs formatter + local markdown saver
├── config.yaml.example            # Project configuration template
├── .env.example                   # API credentials template
├── requirements.txt               # Python dependencies
├── run.sh                         # Cron wrapper script
├── collectors/
│   ├── slack_collector.py         # Slack Web API — messages, threads, decisions
│   ├── slack_mcp_collector.py     # MCP fallback — reads pre-collected Slack JSON
│   ├── jira_collector.py          # Jira REST API — sprint items, blockers, epics
│   ├── jira_mcp_collector.py      # MCP fallback — reads pre-collected Jira JSON
│   ├── gdrive_collector.py        # Google Apps Script Web App — Drive activity
│   └── outlook_collector.py       # Microsoft Graph API — calendar events (optional)
├── google-apps-script/
│   └── Code.gs                    # Google Apps Script for Drive integration
└── output/
    └── newsletter-YYYY-MM-DD.md   # Generated newsletters
```

### How It Works

There are two ways to run the newsletter:

**Option A: Claude Code + MCP (recommended)**
1. Run `/pm-newsletter` in Claude Code
2. Claude collects data via MCP integrations (Slack, Jira) — no API tokens needed
3. Newsletter is published as a **Slack Canvas** or saved as Markdown

**Option B: Standalone Python script**
1. `generate.py` runs collectors that call Slack/Jira/Google Drive APIs directly
2. Claude API synthesizes all data into a newsletter (falls back to template if no API key)
3. Output saved as local Markdown and optionally as a Google Doc

Both approaches produce the same newsletter format. Option A is easier to set up since it uses Claude Code's built-in integrations. Option B is better for automation (cron jobs).

### Data Collection Fallbacks

Each collector has a built-in fallback chain:
- **Slack**: API token → MCP-collected JSON file
- **Jira**: API token → MCP-collected JSON file
- **Google Drive**: Apps Script Web App → skipped gracefully
- **Outlook**: Microsoft Graph API → skipped gracefully

This means the newsletter works even if you only have partial credentials configured.

---

## Setup

### Prerequisites

- Python 3.9+
- Claude Code with Slack MCP connected (for Option A)

### 1. Clone and install

```bash
git clone https://github.com/hehamilton-collab/pm-newsletter.git
cd pm-newsletter
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

### 2. Configure environment

```bash
cp .env.example .env
cp config.yaml.example config.yaml
```

Edit `config.yaml` with your details:

```yaml
user:
  name: "Your Name"
  slack_user_id: "UXXXXXXXXXX"   # Slack profile > ... > Copy member ID
  email: "you@company.com"
  timezone: "America/Los_Angeles"

jira:
  project_key: "YOUR_PROJECT"
  initiative: "Your Initiative"
  components:
    - "Component1"
    - "Component2"
```

---

## Credential Setup

All credentials are optional — the script gracefully skips any collector that isn't configured.

### Slack

**Option A (MCP — no token needed):** If using Claude Code with Slack MCP, data is collected automatically and saved to `output/slack_data.json`. The Python script reads from this file.

**Option B (API token):** Create a Slack app at https://api.slack.com/apps with these **User Token Scopes**: `search:read`, `channels:history`, `groups:history`, `im:history`, `mpim:history`, `users:read`. Add the User OAuth Token to `.env`:
```
SLACK_BOT_TOKEN=xoxp-your-token-here
```

> **Note:** Some enterprise Slack plans restrict app creation. Use the MCP approach instead.

### Jira

**Option A (MCP — no token needed):** If using Claude Code with Jira MCP, data is collected and saved to `output/jira_data.json`.

**Option B (API token):** Generate a personal access token from your Jira profile and add to `.env`:
```
JIRA_SERVER=https://your-jira-instance.com
JIRA_EMAIL=you@company.com
JIRA_API_TOKEN=your-token
```

> **Note:** Some Jira instances require OAuth instead of personal access tokens. Use the MCP approach if you get a 403 error.

### Google Drive (Optional)

Uses a Google Apps Script deployed as a Web App — no Google Cloud Console project needed.

1. Go to [script.google.com](https://script.google.com/) > **New project**
2. Paste contents of `google-apps-script/Code.gs`
3. Deploy as **Web app** (Execute as: Me, Access: Anyone in your org)
4. Add the URL to `.env`:
   ```
   GOOGLE_APPS_SCRIPT_URL=https://script.google.com/.../exec
   ```

### Outlook Calendar (Optional)

Uses Microsoft Graph API. Requires an Azure AD app registration with `Calendars.Read` permission. See `collectors/outlook_collector.py` for details.

> **Note:** Some organizations restrict Azure AD app registration. This collector can be skipped.

### Anthropic API Key (Optional)

Powers AI-synthesized newsletter summaries. Without it, a template formatter is used.

```
ANTHROPIC_API_KEY=sk-ant-...
```

Get a key at https://console.anthropic.com/settings/keys (requires API credits, separate from Claude Pro/Max subscription).

---

## Usage

### Option A: Claude Code (recommended)

```
/pm-newsletter
```

This collects data via MCP, synthesizes the newsletter, and can publish it as a Slack Canvas.

### Option B: Python script

```bash
source venv/bin/activate
python generate.py --skip-outlook --skip-gdrive    # Skip unconfigured collectors
python generate.py --markdown-only                  # Markdown only, no Google Doc
```

### Output formats

- **Slack Canvas** — Best for sharing in your workspace (created via MCP)
- **Google Doc** — Created in a "PM Newsletters" Drive folder (via Apps Script)
- **Markdown** — Saved to `output/newsletter-YYYY-MM-DD.md`

---

## Scheduling

To automate weekly generation via cron:

```bash
crontab -e

# Run every Friday at 12:53 PM (adjust timezone and path):
53 12 * * 5 /path/to/pm-newsletter/run.sh >> /path/to/pm-newsletter/output/cron.log 2>&1
```

---

## Troubleshooting

| Issue | Solution |
|-------|----------|
| Slack `missing_scope` | Use a User OAuth Token (`xoxp-`) instead of Bot Token, or use MCP |
| Jira `403 Forbidden` | Your instance requires OAuth — use MCP fallback instead |
| Jira `401 Unauthorized` | Token expired — regenerate from Jira profile |
| Apps Script date errors | Update to latest `Code.gs` — uses `DriveApp.searchFiles()` not advanced Drive API |
| Claude API billing error | API credits required (separate from Pro/Max subscription) — or skip for template output |
| Enterprise restrictions | Use MCP fallback for Slack/Jira; use Apps Script for Google Drive |

---

## Configuration Reference

### .env variables

| Variable | Required | Description |
|----------|----------|-------------|
| `SLACK_BOT_TOKEN` | Optional | Slack user OAuth token (MCP fallback available) |
| `JIRA_SERVER` | Optional | Jira server URL (MCP fallback available) |
| `JIRA_EMAIL` | Optional | Your Jira email |
| `JIRA_API_TOKEN` | Optional | Jira personal access token |
| `GOOGLE_APPS_SCRIPT_URL` | Optional | Deployed Apps Script Web App URL |
| `MS_CLIENT_ID` | Optional | Azure AD application client ID |
| `MS_TENANT_ID` | Optional | Azure AD directory tenant ID |
| `MS_TOKEN_CACHE` | Optional | Path to Microsoft token cache file |
| `ANTHROPIC_API_KEY` | Optional | Claude API key for AI synthesis |

### config.yaml

See `config.yaml.example` for all available settings including Jira project/components, Slack decision keywords, and lookback period.
