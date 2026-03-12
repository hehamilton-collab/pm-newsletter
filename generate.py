#!/usr/bin/env python3
"""PM Weekly Newsletter Generator.

Collects data from Slack, Jira, Google Drive, and Outlook Calendar,
then uses Claude to synthesize it into a formatted newsletter.
Outputs to a Google Doc and/or local Markdown file.

Usage:
    python generate.py                  # Run with all available collectors
    python generate.py --skip-gdrive    # Skip Google Drive (if not configured)
    python generate.py --skip-outlook   # Skip Outlook (if not configured)
    python generate.py --markdown-only  # Only save as local markdown
"""

import argparse
import json
import os
import sys
from datetime import datetime, timedelta
from pathlib import Path

import yaml
from dotenv import load_dotenv

# Load environment
load_dotenv(Path(__file__).parent / ".env")


def load_config() -> dict:
    """Load configuration from config.yaml."""
    config_path = Path(__file__).parent / "config.yaml"
    with open(config_path) as f:
        return yaml.safe_load(f)


def collect_slack(config: dict) -> dict | None:
    """Collect Slack data."""
    token = os.getenv("SLACK_BOT_TOKEN")
    if not token:
        print("SLACK_BOT_TOKEN not set — skipping Slack collection")
        return None
    from collectors.slack_collector import SlackCollector

    collector = SlackCollector(
        token=token,
        user_id=config["user"]["slack_user_id"],
        lookback_days=config["slack"]["lookback_days"],
    )
    print("Collecting Slack data...")
    return collector.collect()


def collect_jira(config: dict) -> dict | None:
    """Collect Jira data."""
    server = os.getenv("JIRA_SERVER")
    email = os.getenv("JIRA_EMAIL")
    api_token = os.getenv("JIRA_API_TOKEN")
    if not all([server, email, api_token]):
        print("Jira credentials not set — skipping Jira collection")
        return None
    from collectors.jira_collector import JiraCollector

    collector = JiraCollector(
        server=server,
        email=email,
        api_token=api_token,
        project_key=config["jira"]["project_key"],
        components=config["jira"]["components"],
    )
    print("Collecting Jira data...")
    return collector.collect()


def collect_gdrive(config: dict) -> dict | None:
    """Collect Google Drive data via Apps Script Web App."""
    webapp_url = os.getenv("GOOGLE_APPS_SCRIPT_URL")
    if not webapp_url:
        print("GOOGLE_APPS_SCRIPT_URL not set — skipping Google Drive collection")
        return None
    from collectors.gdrive_collector import GDriveCollector

    collector = GDriveCollector(webapp_url=webapp_url)
    return collector.collect()


def collect_outlook(config: dict) -> dict | None:
    """Collect Outlook calendar data."""
    client_id = os.getenv("MS_CLIENT_ID")
    tenant_id = os.getenv("MS_TENANT_ID")
    cache_path = os.getenv("MS_TOKEN_CACHE", "~/.config/pm-newsletter/ms_token_cache.json")
    if not client_id or not tenant_id:
        print("Microsoft credentials not set — skipping Outlook collection")
        return None
    from collectors.outlook_collector import OutlookCollector

    collector = OutlookCollector(
        client_id=client_id,
        tenant_id=tenant_id,
        token_cache_path=cache_path,
    )
    print("Collecting Outlook calendar data...")
    return collector.collect()


def synthesize_newsletter(
    slack_data: dict | None,
    jira_data: dict | None,
    gdrive_data: dict | None,
    outlook_data: dict | None,
    config: dict,
) -> str:
    """Use Claude to synthesize all collected data into a newsletter."""
    api_key = os.getenv("ANTHROPIC_API_KEY")
    if not api_key:
        print("ANTHROPIC_API_KEY not set — using template-based formatting")
        return _template_newsletter(slack_data, jira_data, gdrive_data, outlook_data, config)

    import anthropic

    client = anthropic.Anthropic(api_key=api_key)

    # Build the data payload for Claude
    data_summary = _build_data_summary(slack_data, jira_data, gdrive_data, outlook_data)

    today = datetime.now()
    week_start = (today - timedelta(days=7)).strftime("%B %d")
    week_end = today.strftime("%B %d, %Y")

    prompt = f"""You are generating a PM Weekly Newsletter for {config['user']['name']}, a PM3 Technical at eBay working on the ATMOS board / DP Gateway project (Recoplex, Caramel, Config Hub).

Generate a comprehensive, well-formatted Markdown newsletter for the week of {week_start} – {week_end}.

Use this exact structure:
1. **Executive Summary** (3-5 sentences: what shipped, key decisions, top risks, what needs attention)
2. **Blockers & Risks** (table format with Issue, Story/Thread, Impact, Suggested Action)
3. **Key Decisions & Outcomes** (bullet points with channel and date)
4. **Sprint Status** (health numbers, grouped by epic/work stream, component summaries for Recoplex/Caramel/Config Hub)
5. **Meetings & Context** (past week meetings + upcoming, with attendees) — only if calendar data available
6. **Conversations & Threads** (summarize key threads)
7. **Pending — Needs Your Response** (unanswered questions with suggested starting points)
8. **Document Activity** — only if Google Drive data available
9. **Action Items & Follow-Ups** (prioritized checklist)

Here is the collected data:

{data_summary}

Be specific with Jira ticket numbers, Slack channel names, and people's names. For pending items, provide actionable suggested starting points. Keep the tone professional but direct."""

    print("Synthesizing newsletter with Claude...")
    message = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=8000,
        messages=[{"role": "user", "content": prompt}],
    )
    return message.content[0].text


def _build_data_summary(
    slack_data: dict | None,
    jira_data: dict | None,
    gdrive_data: dict | None,
    outlook_data: dict | None,
) -> str:
    """Build a text summary of all collected data for Claude."""
    parts = []

    if slack_data:
        parts.append("## SLACK DATA")
        parts.append(f"Messages tagging you: {len(slack_data.get('tagged_in', []))}")
        parts.append(f"Messages from you: {len(slack_data.get('from_you', []))}")
        parts.append(f"Decision-related: {len(slack_data.get('decisions', []))}")
        parts.append(f"Questions to you: {len(slack_data.get('questions', []))}")
        parts.append(f"Threads with context: {len(slack_data.get('threads', []))}")

        parts.append("\n### Messages tagging you:")
        for msg in slack_data.get("tagged_in", [])[:30]:
            parts.append(f"- [{msg['timestamp']}] #{msg['channel_name']} @{msg['username']}: {msg['text'][:300]}")

        parts.append("\n### Messages from you:")
        for msg in slack_data.get("from_you", [])[:30]:
            parts.append(f"- [{msg['timestamp']}] #{msg['channel_name']}: {msg['text'][:300]}")

        parts.append("\n### Threads:")
        for thread in slack_data.get("threads", []):
            parts.append(f"\n--- Thread in #{thread['channel_name']} ({thread['reply_count']} replies, your reply: {thread['has_your_reply']}) ---")
            for m in thread["messages"][:10]:
                parts.append(f"  {m['text'][:200]}")

    if jira_data:
        parts.append("\n\n## JIRA DATA")
        health = jira_data.get("sprint_health", {})
        parts.append(f"Sprint: {health.get('total', 0)} total | {health.get('closed', 0)} closed | {health.get('in_progress', 0)} in progress | {health.get('open', 0)} open | {health.get('triage', 0)} triage")

        parts.append("\n### Recently Closed:")
        for item in jira_data.get("recently_closed", []):
            parts.append(f"- {item['key']} — {item['summary']} ({item['priority']}, {item['assignee']})")

        parts.append("\n### In Progress:")
        for item in jira_data.get("status_groups", {}).get("In Progress", []):
            parts.append(f"- {item['key']} — {item['summary']} ({item['priority']}, {item['assignee']})")

        parts.append("\n### Blockers/High Priority:")
        for item in jira_data.get("blockers", []):
            parts.append(f"- {item['key']} — {item['summary']} (Status: {item['status']}, {item['priority']}, {item['assignee']})")

        parts.append("\n### DP Gateway Items:")
        for item in jira_data.get("dp_gateway", []):
            parts.append(f"- {item['key']} — {item['summary']} (Status: {item['status']}, {item['assignee']})")

    if gdrive_data:
        parts.append("\n\n## GOOGLE DRIVE DATA")
        parts.append("\n### Modified Documents:")
        for doc in gdrive_data.get("modified_documents", [])[:20]:
            parts.append(f"- [{doc['type']}] {doc['name']} — modified by {doc['last_modified_by']} at {doc['modified_time']}")
        parts.append("\n### Activity:")
        for act in gdrive_data.get("activity", [])[:20]:
            parts.append(f"- {act['action']}: {act['name']} by {act['actor']}")

    if outlook_data:
        parts.append("\n\n## OUTLOOK CALENDAR DATA")
        parts.append("\n### Past Week Meetings:")
        for event in outlook_data.get("past_events", [])[:20]:
            attendee_names = ", ".join(a["name"] for a in event["attendees"][:5])
            parts.append(f"- {event['subject']} | {event['start'][:16]} | with: {attendee_names}")
        parts.append("\n### Upcoming Meetings:")
        for event in outlook_data.get("upcoming_events", [])[:20]:
            attendee_names = ", ".join(a["name"] for a in event["attendees"][:5])
            parts.append(f"- {event['subject']} | {event['start'][:16]} | with: {attendee_names}")
        parts.append("\n### People Met (by frequency):")
        for person in outlook_data.get("people_met", [])[:15]:
            parts.append(f"- {person['name']} ({person['meeting_count']} meetings)")

    return "\n".join(parts)


def _template_newsletter(
    slack_data: dict | None,
    jira_data: dict | None,
    gdrive_data: dict | None,
    outlook_data: dict | None,
    config: dict,
) -> str:
    """Fallback: generate newsletter using simple template (no Claude API)."""
    today = datetime.now()
    week_start = (today - timedelta(days=7)).strftime("%B %d")
    week_end = today.strftime("%B %d, %Y")

    sections = [f"# PM Weekly Newsletter — Week of {week_start} – {week_end}\n"]
    sections.append("---\n")

    # Executive Summary placeholder
    sections.append("## Executive Summary\n")
    if jira_data:
        h = jira_data["sprint_health"]
        sections.append(f"Sprint: {h['closed']} closed | {h['in_progress']} in progress | {h['open']} open | {h['triage']} triage\n")
    if slack_data:
        sections.append(f"Slack: {len(slack_data.get('tagged_in', []))} messages tagging you | {len(slack_data.get('from_you', []))} from you\n")
    sections.append("")

    # Blockers
    if jira_data and jira_data.get("blockers"):
        sections.append("## Blockers & Risks\n")
        sections.append("| Issue | Key | Priority | Assignee | Status |")
        sections.append("|-------|-----|----------|----------|--------|")
        for item in jira_data["blockers"][:15]:
            sections.append(f"| {item['summary'][:50]} | {item['key']} | {item['priority']} | {item['assignee']} | {item['status']} |")
        sections.append("")

    # Recently Closed
    if jira_data and jira_data.get("recently_closed"):
        sections.append("## Closed This Week\n")
        for item in jira_data["recently_closed"]:
            sections.append(f"- **{item['key']}** — {item['summary']} ({item['assignee']})")
        sections.append("")

    # In Progress
    if jira_data:
        in_progress = jira_data.get("status_groups", {}).get("In Progress", [])
        if in_progress:
            sections.append("## In Progress\n")
            for item in in_progress:
                sections.append(f"- **{item['key']}** — {item['summary']} ({item['priority']}, {item['assignee']})")
            sections.append("")

    # Calendar
    if outlook_data:
        sections.append("## Meetings & Calendar\n")
        sections.append("### Past Week")
        for event in outlook_data.get("past_events", [])[:15]:
            attendees = ", ".join(a["name"] for a in event["attendees"][:4])
            sections.append(f"- **{event['subject']}** — {event['start'][:16]} — with {attendees}")
        sections.append("\n### Upcoming")
        for event in outlook_data.get("upcoming_events", [])[:15]:
            attendees = ", ".join(a["name"] for a in event["attendees"][:4])
            sections.append(f"- **{event['subject']}** — {event['start'][:16]} — with {attendees}")
        sections.append("")

    # Google Drive
    if gdrive_data and gdrive_data.get("modified_documents"):
        sections.append("## Document Activity\n")
        for doc in gdrive_data["modified_documents"][:15]:
            sections.append(f"- [{doc['type']}] **{doc['name']}** — modified by {doc['last_modified_by']}")
        sections.append("")

    sections.append(f"\n---\n*Generated on {today.strftime('%Y-%m-%d %H:%M')} by PM Newsletter Bot*")
    return "\n".join(sections)


def main():
    parser = argparse.ArgumentParser(description="PM Weekly Newsletter Generator")
    parser.add_argument("--skip-gdrive", action="store_true", help="Skip Google Drive collection")
    parser.add_argument("--skip-outlook", action="store_true", help="Skip Outlook collection")
    parser.add_argument("--markdown-only", action="store_true", help="Only save as markdown (no Google Doc)")
    args = parser.parse_args()

    config = load_config()
    print(f"Generating newsletter for {config['user']['name']}...\n")

    # Collect data from all sources
    slack_data = collect_slack(config)
    jira_data = collect_jira(config)
    gdrive_data = None if args.skip_gdrive else collect_gdrive(config)
    outlook_data = None if args.skip_outlook else collect_outlook(config)

    # Synthesize into newsletter
    newsletter = synthesize_newsletter(
        slack_data, jira_data, gdrive_data, outlook_data, config
    )

    # Save as markdown
    from formatter import save_markdown

    md_path = save_markdown(newsletter, config["newsletter"]["output_dir"])

    # Create Google Doc via Apps Script if configured and not markdown-only
    if not args.markdown_only:
        webapp_url = os.getenv("GOOGLE_APPS_SCRIPT_URL")
        if webapp_url:
            from collectors.gdrive_collector import GDriveCollector

            today = datetime.now()
            title = f"PM Newsletter — {today.strftime('%B %d, %Y')}"
            gdrive = GDriveCollector(webapp_url=webapp_url)
            doc_url = gdrive.create_newsletter_doc(title, newsletter)
            if doc_url:
                print(f"\nGoogle Doc: {doc_url}")
        else:
            print("\nGoogle Doc output skipped (GOOGLE_APPS_SCRIPT_URL not set)")

    print(f"\nMarkdown: {md_path}")
    print("Done!")


if __name__ == "__main__":
    main()
