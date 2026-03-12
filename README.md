# PM Weekly Newsletter Generator

Automated weekly newsletter for PM3 Technical — eBay ATMOS / DP Gateway. Pulls data from Slack, Jira, Google Drive, and Outlook Calendar, then uses Claude to synthesize it into a formatted newsletter with executive summary, sprint status, blockers, key decisions, and action items.

## Newsletter Sections

1. **Executive Summary** — 3-5 sentences: what shipped, key decisions, top risks, what needs attention
2. **Blockers & Risks** — Table of stuck stories, P1/P2s, dependencies at risk with suggested actions
3. **Key Decisions & Outcomes** — Decisions made in Slack with channel and date
4. **Sprint Status** — Health numbers, grouped by epic/work stream, component summaries (Recoplex, Caramel, Config Hub)
5. **Meetings & Context** — Past + upcoming meetings with attendees (requires Outlook setup)
6. **Conversations & Threads** — Key Slack thread summaries
7. **Pending — Needs Your Response** — Unanswered questions with suggested starting points
8. **Document Activity** — Recently modified Google Drive files (requires Google Drive setup)
9. **Action Items & Follow-Ups** — Prioritized checklist

## Architecture

```
pm-newsletter/
├── generate.py              # Main orchestrator — runs all collectors, synthesizes newsletter
├── formatter.py             # Google Docs formatter + local markdown saver
├── config.yaml              # Project configuration (user, Jira, Slack settings)
├── .env                     # API credentials (not committed)
├── .env.example             # Template for .env
├── requirements.txt         # Python dependencies
├── run.sh                   # Cron wrapper script
├── collectors/
│   ├── slack_collector.py   # Slack Web API — messages, threads, decisions
│   ├── jira_collector.py    # Jira REST API — sprint items, blockers, epics
│   ├── gdrive_collector.py  # Google Apps Script Web App — Drive activity
│   └── outlook_collector.py # Microsoft Graph API — calendar events
├── google-apps-script/
│   └── Code.gs              # Google Apps Script (deploy as Web App)
└── output/
    └── newsletter-YYYY-MM-DD.md  # Generated newsletters
```

### How It Works

1. **Collectors** pull data from each source (Slack, Jira, Google Drive, Outlook)
2. **Claude API** synthesizes all collected data into a structured newsletter (falls back to a template if no API key is set)
3. **Output** is saved as local Markdown and optionally as a Google Doc (via the Apps Script Web App)

### Google Apps Script Web App

Because eBay's Google Workspace restricts Google Cloud Console access, Google Drive integration uses a **Google Apps Script** deployed as a Web App instead of direct API credentials. The script:
- Runs inside your eBay Google account with built-in Drive access
- Exposes GET (fetch Drive activity) and POST (create newsletter Google Doc) endpoints
- No Cloud Console project or OAuth credentials needed

---

## Setup

### Prerequisites

- Python 3.11+
- An eBay Google Workspace account (for Google Apps Script)
- Access to Jira (jirap.corp.ebay.com)
- A Slack workspace with bot token access

### 1. Clone and install

```bash
cd ~/pm-newsletter
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

### 2. Configure environment

```bash
cp .env.example .env
```

Edit `.env` and fill in credentials as you complete each section below.

### 3. Configure project settings

Copy the example and edit with your details:

```bash
cp config.yaml.example config.yaml
```

Edit `config.yaml` to match your setup:

```yaml
user:
  name: "Your Name"
  slack_user_id: "U052DK3HMRC"   # Find via Slack profile > ... > Copy member ID
  email: "you@ebay.com"
  timezone: "America/Los_Angeles"

jira:
  project_key: "ATMOS"
  initiative: "DP Gateway"
  components:
    - "Recoplex"
    - "Caramel"
    - "Config Hub"
    - "DP Gateway"
```

---

## Credential Setup

### Jira API Token

The Jira collector uses basic auth against `jirap.corp.ebay.com`.

1. Go to your Jira profile: **Profile > Personal Access Tokens** (or navigate to `https://jirap.corp.ebay.com/secure/ViewProfile.jspa` > **Personal Access Tokens**)
2. If your Jira instance uses Atlassian Cloud, go to https://id.atlassian.com/manage-profile/security/api-tokens instead
3. Click **Create token**
4. Name it `pm-newsletter` and copy the token
5. Add to `.env`:
   ```
   JIRA_SERVER=https://jirap.corp.ebay.com
   JIRA_EMAIL=hehamilton@ebay.com
   JIRA_API_TOKEN=<your-token>
   ```

> **Note:** If your Jira instance uses SSO/OAuth and doesn't support personal access tokens, you may need to use a service account or ask your Jira admin for API access.

### Slack Bot Token

The Slack collector uses the Slack Web API for searching messages and fetching threads.

1. Go to https://api.slack.com/apps
2. Click **Create New App** > **From scratch**
3. Name: `PM Newsletter`, Workspace: your eBay workspace
4. Go to **OAuth & Permissions** in the sidebar
5. Under **Bot Token Scopes**, add:
   - `search:read` — search messages
   - `channels:history` — read public channel messages
   - `groups:history` — read private channel messages
   - `im:history` — read DM messages
   - `mpim:history` — read group DM messages
   - `users:read` — look up user info
6. Click **Install to Workspace** and authorize
7. Copy the **Bot User OAuth Token** (starts with `xoxb-`)
8. Add to `.env`:
   ```
   SLACK_BOT_TOKEN=xoxb-your-token-here
   ```

> **Note:** The `search:read` scope requires a **user token** (`xoxp-`), not a bot token, on some Slack plans. If search doesn't work with the bot token, go to **OAuth & Permissions** > **User Token Scopes** and add `search:read` there, then use the **User OAuth Token** instead.

### Google Drive (Apps Script Web App)

This is already set up if you completed the original session. If not:

1. Go to [script.google.com](https://script.google.com/) and click **New project**
2. Name it **"PM Newsletter"**
3. Delete all code in the editor
4. Copy the contents of `google-apps-script/Code.gs` and paste it in
5. Click **Save**
6. Test it:
   - Select **`testDriveActivity`** from the function dropdown
   - Click **Run**
   - First time: authorize all permissions when prompted
   - Check Execution log — should show modified files count
7. Deploy as Web App:
   - Click **Deploy** > **New deployment**
   - Type: **Web app**
   - Execute as: **Me**
   - Who has access: **Anyone** (within your org) or **Anyone with Google account**
   - Click **Deploy** and copy the Web App URL
8. Add to `.env`:
   ```
   GOOGLE_APPS_SCRIPT_URL=https://script.google.com/a/macros/ebay.com/s/.../exec
   ```

**To verify the deployment works:**
```bash
curl "YOUR_APPS_SCRIPT_URL?action=health"
# Should return: {"status":"ok","timestamp":"..."}
```

### Outlook Calendar (Microsoft Graph / Azure AD)

This integration pulls your past and upcoming calendar events via the Microsoft Graph API.

1. Go to [Azure Portal > App Registrations](https://portal.azure.com/#view/Microsoft_AAD_RegisteredApps/ApplicationsListBlade)
2. Sign in with your eBay Microsoft account
3. Click **New registration**:
   - Name: `PM Newsletter`
   - Supported account types: **"Accounts in this organizational directory only"** (eBay tenant)
   - Redirect URI: leave blank for now
   - Click **Register**
4. On the app overview page, copy:
   - **Application (client) ID**
   - **Directory (tenant) ID**
5. Go to **API permissions** > **Add a permission**:
   - Select **Microsoft Graph**
   - Select **Delegated permissions**
   - Search and add: `Calendars.Read`
   - Click **Add permissions**
6. Go to **Authentication** > **Add a platform**:
   - Select **Mobile and desktop applications**
   - Check the `https://login.microsoftonline.com/common/oauth2/nativeclient` redirect URI
   - Click **Configure**
7. Add to `.env`:
   ```
   MS_CLIENT_ID=your-application-client-id
   MS_TENANT_ID=your-directory-tenant-id
   MS_TOKEN_CACHE=~/.config/pm-newsletter/ms_token_cache.json
   ```
8. On first run, the script will print a device code URL and code. Open the URL in your browser, enter the code, and sign in with your eBay Microsoft account. After that, the token is cached.

> **Note:** If your organization requires admin consent for Graph API permissions, you'll need to ask your Azure AD admin to grant consent for the `Calendars.Read` permission on your app registration.

### Anthropic API Key (Optional)

The Claude API is used to synthesize all collected data into a well-written newsletter. Without it, a basic template-based formatter is used instead.

1. Go to https://console.anthropic.com/settings/keys
2. Click **Create Key**
3. Name it `pm-newsletter` and copy the key
4. Add to `.env`:
   ```
   ANTHROPIC_API_KEY=sk-ant-...
   ```

---

## Usage

### Run manually

```bash
source venv/bin/activate
python generate.py
```

### Skip specific collectors

```bash
python generate.py --skip-gdrive      # Skip Google Drive (if not configured)
python generate.py --skip-outlook      # Skip Outlook (if not configured)
python generate.py --markdown-only     # Only save as markdown, no Google Doc
```

### Run via shell script

```bash
./run.sh
```

### Output

- **Markdown:** `output/newsletter-YYYY-MM-DD.md`
- **Google Doc:** Created in a "PM Newsletters" folder in your Google Drive (if Apps Script is configured)

### Using the Claude Code slash command

If you're in Claude Code, you can generate the newsletter using the MCP-connected approach (Slack + Jira MCP tools directly, no API tokens needed):

```
/pm-newsletter
```

This uses Claude Code's built-in Slack and Jira integrations and doesn't require the Python API tokens.

---

## Scheduling (Cron)

To run every Friday at 12:53 PM PT (before the 1pm deadline):

```bash
# Edit your crontab
crontab -e

# Add this line (adjust path as needed):
53 12 * * 5 /Users/hehamilton/pm-newsletter/run.sh >> /Users/hehamilton/pm-newsletter/output/cron.log 2>&1
```

Or use `launchd` on macOS for more reliable scheduling:

```bash
# Create ~/Library/LaunchAgents/com.pm-newsletter.plist
# See Apple docs for launchd plist format
```

---

## Troubleshooting

### Slack: "missing_scope" error
Your token may need user-level scopes (especially `search:read`). Try using a **User OAuth Token** (`xoxp-`) instead of the Bot Token.

### Jira: "401 Unauthorized"
Your API token may have expired or your Jira instance may not support personal access tokens. Check with your Jira admin.

### Google Apps Script: "TypeError" or date format errors
Make sure you're using the latest version of `Code.gs` from this repo. The script uses `DriveApp.searchFiles()` (not the advanced Drive API) to avoid date format issues.

### Outlook: "AADSTS65001" (consent required)
Your Azure AD admin needs to grant consent for the `Calendars.Read` permission. Ask your admin or try the **Grant admin consent** button in the Azure Portal.

### Claude API: falls back to template
If `ANTHROPIC_API_KEY` is not set, the script uses a basic template formatter instead of Claude-powered synthesis. The template includes the same data but without AI-written summaries.

---

## Configuration Reference

### .env variables

| Variable | Required | Description |
|----------|----------|-------------|
| `SLACK_BOT_TOKEN` | For Slack | Slack bot or user OAuth token |
| `JIRA_SERVER` | For Jira | Jira server URL |
| `JIRA_EMAIL` | For Jira | Your Jira email |
| `JIRA_API_TOKEN` | For Jira | Jira personal access token |
| `GOOGLE_APPS_SCRIPT_URL` | For Google Drive | Deployed Apps Script Web App URL |
| `MS_CLIENT_ID` | For Outlook | Azure AD application client ID |
| `MS_TENANT_ID` | For Outlook | Azure AD directory tenant ID |
| `MS_TOKEN_CACHE` | For Outlook | Path to Microsoft token cache file |
| `ANTHROPIC_API_KEY` | Optional | Claude API key for AI synthesis |

### config.yaml

See [config.yaml](config.yaml) for all available settings including Jira project/components, Slack decision keywords, and lookback period.
