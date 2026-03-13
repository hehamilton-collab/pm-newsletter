"""Outlook Calendar data collector via Microsoft Graph API."""

from __future__ import annotations

import json
import os
from datetime import datetime, timedelta, timezone

import msal
import requests

GRAPH_API = "https://graph.microsoft.com/v1.0"
SCOPES = ["Calendars.Read"]


class OutlookCollector:
    def __init__(
        self,
        client_id: str,
        tenant_id: str,
        token_cache_path: str,
        lookback_days: int = 7,
        lookahead_days: int = 7,
    ):
        self.client_id = client_id
        self.tenant_id = tenant_id
        self.token_cache_path = os.path.expanduser(token_cache_path)
        self.lookback_days = lookback_days
        self.lookahead_days = lookahead_days
        self.access_token = self._authenticate()

    def collect(self) -> dict:
        """Collect calendar events for past and upcoming week."""
        now = datetime.now(timezone.utc)
        past_start = now - timedelta(days=self.lookback_days)
        future_end = now + timedelta(days=self.lookahead_days)

        past_events = self._get_events(past_start, now)
        upcoming_events = self._get_events(now, future_end)

        # Extract unique attendees and meeting patterns
        people_met = self._extract_people(past_events)
        recurring = self._identify_recurring(past_events + upcoming_events)

        return {
            "past_events": past_events,
            "upcoming_events": upcoming_events,
            "people_met": people_met,
            "recurring_meetings": recurring,
        }

    def _get_events(self, start: datetime, end: datetime) -> list[dict]:
        """Fetch calendar events in a time range."""
        headers = {
            "Authorization": f"Bearer {self.access_token}",
            "Content-Type": "application/json",
        }
        params = {
            "startDateTime": start.isoformat(),
            "endDateTime": end.isoformat(),
            "$orderby": "start/dateTime",
            "$top": 100,
            "$select": "subject,start,end,attendees,organizer,isAllDay,recurrence,location,bodyPreview",
        }
        events = []
        try:
            response = requests.get(
                f"{GRAPH_API}/me/calendarView",
                headers=headers,
                params=params,
                timeout=30,
            )
            response.raise_for_status()
            data = response.json()
            for event in data.get("value", []):
                events.append({
                    "subject": event.get("subject", "No Subject"),
                    "start": event["start"]["dateTime"],
                    "end": event["end"]["dateTime"],
                    "is_all_day": event.get("isAllDay", False),
                    "organizer": (
                        event.get("organizer", {})
                        .get("emailAddress", {})
                        .get("name", "Unknown")
                    ),
                    "attendees": [
                        {
                            "name": a.get("emailAddress", {}).get("name", ""),
                            "email": a.get("emailAddress", {}).get("address", ""),
                            "response": a.get("status", {}).get("response", ""),
                        }
                        for a in event.get("attendees", [])
                    ],
                    "location": event.get("location", {}).get("displayName", ""),
                    "is_recurring": event.get("recurrence") is not None,
                    "preview": event.get("bodyPreview", "")[:200],
                })
        except requests.RequestException as e:
            print(f"Outlook API error: {e}")
        return events

    def _extract_people(self, events: list[dict]) -> list[dict]:
        """Extract unique people you met with and meeting counts."""
        people = {}
        for event in events:
            for attendee in event.get("attendees", []):
                name = attendee["name"]
                if name and name not in people:
                    people[name] = {"name": name, "email": attendee["email"], "meeting_count": 0}
                if name:
                    people[name]["meeting_count"] += 1

        return sorted(people.values(), key=lambda p: p["meeting_count"], reverse=True)

    @staticmethod
    def _identify_recurring(events: list[dict]) -> list[dict]:
        """Identify recurring meetings by subject pattern."""
        recurring = {}
        for event in events:
            if event.get("is_recurring"):
                subject = event["subject"]
                if subject not in recurring:
                    recurring[subject] = {
                        "subject": subject,
                        "organizer": event["organizer"],
                        "occurrences": 0,
                    }
                recurring[subject]["occurrences"] += 1
        return list(recurring.values())

    def _authenticate(self) -> str:
        """Authenticate with Microsoft Graph using device code flow."""
        cache = msal.SerializableTokenCache()
        if os.path.exists(self.token_cache_path):
            with open(self.token_cache_path, "r") as f:
                cache.deserialize(f.read())

        app = msal.PublicClientApplication(
            self.client_id,
            authority=f"https://login.microsoftonline.com/{self.tenant_id}",
            token_cache=cache,
        )

        accounts = app.get_accounts()
        result = None
        if accounts:
            result = app.acquire_token_silent(SCOPES, account=accounts[0])

        if not result:
            flow = app.initiate_device_flow(scopes=SCOPES)
            if "user_code" not in flow:
                raise ValueError(f"Failed to create device flow: {flow}")
            print(f"\nTo sign in, visit: {flow['verification_uri']}")
            print(f"Enter code: {flow['user_code']}\n")
            result = app.acquire_token_by_device_flow(flow)

        if "access_token" not in result:
            raise ValueError(f"Authentication failed: {result.get('error_description', 'Unknown error')}")

        # Save cache
        if cache.has_state_changed:
            os.makedirs(os.path.dirname(self.token_cache_path), exist_ok=True)
            with open(self.token_cache_path, "w") as f:
                f.write(cache.serialize())

        return result["access_token"]
