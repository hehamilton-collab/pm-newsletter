"""Slack data collector for PM Newsletter."""

from __future__ import annotations

import time
from datetime import datetime, timedelta
from slack_sdk import WebClient
from slack_sdk.errors import SlackApiError


class SlackCollector:
    def __init__(self, token: str, user_id: str, lookback_days: int = 7):
        self.client = WebClient(token=token)
        self.user_id = user_id
        self.lookback_days = lookback_days
        self.oldest = str(
            int((datetime.now() - timedelta(days=lookback_days)).timestamp())
        )

    def collect(self) -> dict:
        """Collect all Slack data for the newsletter."""
        tagged_in = self._search(f"to:<@{self.user_id}>")
        from_you = self._search(f"from:<@{self.user_id}>")
        decisions = self._search_decisions()
        questions = self._search(f"to:<@{self.user_id}> ?")

        # Deduplicate and enrich with thread context for high-signal messages
        threads = self._get_thread_context(tagged_in + questions)

        return {
            "tagged_in": tagged_in,
            "from_you": from_you,
            "decisions": decisions,
            "questions": questions,
            "threads": threads,
        }

    def _search(self, query: str, max_results: int = 50) -> list[dict]:
        """Search Slack messages."""
        results = []
        try:
            response = self.client.search_messages(
                query=f"{query} after:{self._date_str()}",
                sort="timestamp",
                sort_dir="desc",
                count=min(max_results, 100),
            )
            for match in response.get("messages", {}).get("matches", []):
                results.append(self._parse_message(match))
        except SlackApiError as e:
            print(f"Slack search error for '{query}': {e.response['error']}")
        return results

    def _search_decisions(self) -> list[dict]:
        """Search for decision-related messages across channels."""
        keywords = ["decision", "agreed", "approved", "aligned", "sign off", "shipping"]
        all_results = []
        seen_ts = set()
        for keyword in keywords:
            for msg in self._search(keyword, max_results=10):
                if msg["ts"] not in seen_ts:
                    seen_ts.add(msg["ts"])
                    all_results.append(msg)
            time.sleep(0.5)  # Rate limiting
        return all_results

    def _get_thread_context(self, messages: list[dict], max_threads: int = 15) -> list[dict]:
        """Fetch full thread context for messages that have replies."""
        threads = []
        seen = set()
        for msg in messages[:max_threads]:
            thread_ts = msg.get("thread_ts") or msg.get("ts")
            channel = msg.get("channel_id")
            key = f"{channel}:{thread_ts}"
            if key in seen or not channel:
                continue
            seen.add(key)
            try:
                response = self.client.conversations_replies(
                    channel=channel,
                    ts=thread_ts,
                    limit=20,
                )
                thread_messages = response.get("messages", [])
                if len(thread_messages) > 1:  # Only include actual threads
                    threads.append({
                        "channel_id": channel,
                        "channel_name": msg.get("channel_name", ""),
                        "thread_ts": thread_ts,
                        "messages": [self._parse_reply(m) for m in thread_messages],
                        "reply_count": len(thread_messages) - 1,
                        "has_your_reply": any(
                            m.get("user") == self.user_id
                            for m in thread_messages[1:]
                        ),
                    })
                time.sleep(0.3)  # Rate limiting
            except SlackApiError:
                continue
        return threads

    def _parse_message(self, match: dict) -> dict:
        """Parse a Slack search result into a clean dict."""
        return {
            "text": match.get("text", ""),
            "user": match.get("user", ""),
            "username": match.get("username", ""),
            "channel_id": match.get("channel", {}).get("id", ""),
            "channel_name": match.get("channel", {}).get("name", ""),
            "ts": match.get("ts", ""),
            "thread_ts": match.get("thread_ts"),
            "permalink": match.get("permalink", ""),
            "timestamp": datetime.fromtimestamp(
                float(match.get("ts", "0"))
            ).strftime("%Y-%m-%d %H:%M"),
        }

    def _parse_reply(self, msg: dict) -> dict:
        """Parse a thread reply message."""
        return {
            "text": msg.get("text", ""),
            "user": msg.get("user", ""),
            "ts": msg.get("ts", ""),
        }

    def _date_str(self) -> str:
        """Get the lookback date as YYYY-MM-DD string."""
        return (datetime.now() - timedelta(days=self.lookback_days)).strftime(
            "%Y-%m-%d"
        )
