"""Slack data collector that reads from a pre-collected JSON file.

Instead of using the Slack API directly (which requires a bot token),
this collector reads Slack data that was collected via Claude Code's
MCP Slack integration and saved as a JSON file.

Usage:
    1. Run the Claude Code /pm-newsletter command or collect_slack.py
       to collect Slack data via MCP and save to output/slack_data.json
    2. generate.py will automatically read from that file
"""

from __future__ import annotations

import json
import os
from datetime import datetime, timedelta
from pathlib import Path


class SlackMCPCollector:
    """Reads Slack data from a JSON file collected via MCP."""

    def __init__(self, data_file: str = None):
        if data_file is None:
            data_file = str(Path(__file__).parent.parent / "output" / "slack_data.json")
        self.data_file = os.path.expanduser(data_file)

    def collect(self) -> dict | None:
        """Read Slack data from the JSON file."""
        if not os.path.exists(self.data_file):
            print(f"Slack data file not found: {self.data_file}")
            print("Run the /pm-newsletter command in Claude Code first to collect Slack data via MCP.")
            return None

        # Check if data is stale (older than 24 hours)
        file_age = datetime.now().timestamp() - os.path.getmtime(self.data_file)
        if file_age > 86400:
            age_hours = int(file_age / 3600)
            print(f"Warning: Slack data is {age_hours} hours old. Consider re-collecting via /pm-newsletter.")

        with open(self.data_file) as f:
            data = json.load(f)

        msg_count = len(data.get("tagged_in", []))
        thread_count = len(data.get("threads", []))
        print(f"Loaded Slack data: {msg_count} messages, {thread_count} threads")
        return data
