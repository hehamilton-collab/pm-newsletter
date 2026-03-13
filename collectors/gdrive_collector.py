"""Google Drive data collector for PM Newsletter.

Uses the Google Apps Script Web App endpoint to fetch Drive activity.
No Google Cloud project or OAuth setup needed — the Apps Script handles auth.
"""

from __future__ import annotations

import requests


class GDriveCollector:
    def __init__(self, webapp_url: str):
        self.webapp_url = webapp_url

    def collect(self) -> dict:
        """Fetch Drive activity from the Apps Script Web App."""
        print("Fetching Google Drive activity...")
        try:
            # GET request returns modified files + shared files
            response = requests.get(
                self.webapp_url,
                params={"action": "activity"},
                timeout=60,
            )
            response.raise_for_status()
            data = response.json()
            return {
                "modified_documents": data.get("modified_files", []),
                "shared_with_me": data.get("shared_with_me", []),
                "collected_at": data.get("collected_at", ""),
            }
        except requests.RequestException as e:
            print(f"Google Drive collector error: {e}")
            return {"modified_documents": [], "shared_with_me": []}

    def create_newsletter_doc(self, title: str, content: str) -> str | None:
        """Create a Google Doc via the Apps Script Web App.

        Returns the URL of the created document.
        """
        print("Creating Google Doc newsletter...")
        try:
            response = requests.post(
                self.webapp_url,
                json={"title": title, "content": content},
                timeout=120,
            )
            response.raise_for_status()
            data = response.json()
            if data.get("success"):
                print(f"Google Doc created: {data['url']}")
                return data["url"]
            else:
                print(f"Failed to create doc: {data.get('error', 'Unknown error')}")
                return None
        except requests.RequestException as e:
            print(f"Google Doc creation error: {e}")
            return None
