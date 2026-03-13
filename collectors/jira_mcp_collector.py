"""Jira data collector that reads from a pre-collected JSON file.

Instead of using the Jira API directly (which requires OAuth on some instances),
this collector reads Jira data that was collected via Claude Code's MCP Jira
integration and saved as a JSON file.

Usage:
    1. Run the Claude Code /pm-newsletter command to collect Jira data via MCP
       and save to output/jira_data.json
    2. generate.py will automatically read from that file
"""

from __future__ import annotations

import json
import os
from datetime import datetime
from pathlib import Path


class JiraMCPCollector:
    """Reads Jira data from a JSON file collected via MCP."""

    def __init__(self, data_file: str | None = None):
        if data_file is None:
            data_file = str(Path(__file__).parent.parent / "output" / "jira_data.json")
        self.data_file = os.path.expanduser(data_file)

    def collect(self) -> dict | None:
        """Read Jira data from the JSON file."""
        if not os.path.exists(self.data_file):
            print(f"Jira data file not found: {self.data_file}")
            print("Run the /pm-newsletter command in Claude Code first to collect Jira data via MCP.")
            return None

        file_age = datetime.now().timestamp() - os.path.getmtime(self.data_file)
        if file_age > 86400:
            age_hours = int(file_age / 3600)
            print(f"Warning: Jira data is {age_hours} hours old. Consider re-collecting via /pm-newsletter.")

        with open(self.data_file) as f:
            data = json.load(f)

        total = data.get("sprint_health", {}).get("total", 0)
        closed = data.get("sprint_health", {}).get("closed", 0)
        print(f"Loaded Jira data: {total} sprint items, {closed} closed")
        return data
