"""Newsletter formatter — generates Google Doc and local Markdown."""

from __future__ import annotations

import os
from datetime import datetime, timedelta

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build

SCOPES = ["https://www.googleapis.com/auth/documents", "https://www.googleapis.com/auth/drive.file"]


class GoogleDocFormatter:
    """Creates or updates a Google Doc with the newsletter content."""

    def __init__(self, credentials_file: str, token_file: str, folder_id: str = ""):
        self.credentials_file = os.path.expanduser(credentials_file)
        self.token_file = os.path.expanduser(token_file)
        self.folder_id = folder_id
        self.creds = self._authenticate()
        self.docs_service = build("docs", "v1", credentials=self.creds)
        self.drive_service = build("drive", "v3", credentials=self.creds)

    def create_newsletter(self, markdown_content: str, title: str) -> str:
        """Create a new Google Doc with the newsletter content.

        Returns the URL of the created document.
        """
        # Create the document
        doc = self.docs_service.documents().create(body={"title": title}).execute()
        doc_id = doc["documentId"]

        # Move to folder if specified
        if self.folder_id:
            self.drive_service.files().update(
                fileId=doc_id,
                addParents=self.folder_id,
                fields="id, parents",
            ).execute()

        # Convert markdown to Google Docs requests
        requests = self._markdown_to_doc_requests(markdown_content)
        if requests:
            self.docs_service.documents().batchUpdate(
                documentId=doc_id, body={"requests": requests}
            ).execute()

        doc_url = f"https://docs.google.com/document/d/{doc_id}/edit"
        print(f"Newsletter created: {doc_url}")
        return doc_url

    def _markdown_to_doc_requests(self, markdown: str) -> list[dict]:
        """Convert markdown content to Google Docs API batch update requests."""
        requests = []
        lines = markdown.split("\n")
        index = 1  # Google Docs index starts at 1

        for line in lines:
            if not line and requests:
                # Empty line = paragraph break
                text = "\n"
                requests.append({
                    "insertText": {"location": {"index": index}, "text": text}
                })
                index += len(text)
                continue

            # Determine heading level and style
            heading_style = None
            if line.startswith("# "):
                line = line[2:]
                heading_style = "HEADING_1"
            elif line.startswith("## "):
                line = line[3:]
                heading_style = "HEADING_2"
            elif line.startswith("### "):
                line = line[4:]
                heading_style = "HEADING_3"
            elif line.startswith("---"):
                line = "━" * 60
            elif line.startswith("- **"):
                # Bold list item — keep as is, we'll style inline
                pass
            elif line.startswith("| "):
                # Table row — convert to tab-separated
                cells = [c.strip() for c in line.split("|")[1:-1]]
                line = "\t".join(cells)

            text = line + "\n"
            requests.append({
                "insertText": {"location": {"index": index}, "text": text}
            })

            if heading_style:
                requests.append({
                    "updateParagraphStyle": {
                        "range": {
                            "startIndex": index,
                            "endIndex": index + len(text),
                        },
                        "paragraphStyle": {"namedStyleType": heading_style},
                        "fields": "namedStyleType",
                    }
                })

            # Bold text between ** markers
            import re
            for match in re.finditer(r"\*\*(.+?)\*\*", line):
                bold_start = index + match.start()
                bold_end = index + match.end()
                requests.append({
                    "updateTextStyle": {
                        "range": {"startIndex": bold_start, "endIndex": bold_end},
                        "textStyle": {"bold": True},
                        "fields": "bold",
                    }
                })

            index += len(text)

        return requests

    def _authenticate(self) -> Credentials:
        """Authenticate with Google APIs."""
        creds = None
        if os.path.exists(self.token_file):
            creds = Credentials.from_authorized_user_file(self.token_file, SCOPES)
        if not creds or not creds.valid:
            if creds and creds.expired and creds.refresh_token:
                creds.refresh(Request())
            else:
                flow = InstalledAppFlow.from_client_secrets_file(
                    self.credentials_file, SCOPES
                )
                creds = flow.run_local_server(port=0)
            os.makedirs(os.path.dirname(self.token_file), exist_ok=True)
            with open(self.token_file, "w") as token:
                token.write(creds.to_json())
        return creds


def save_markdown(content: str, output_dir: str) -> str:
    """Save newsletter as local markdown file."""
    output_dir = os.path.expanduser(output_dir)
    os.makedirs(output_dir, exist_ok=True)
    date_str = datetime.now().strftime("%Y-%m-%d")
    filepath = os.path.join(output_dir, f"newsletter-{date_str}.md")
    with open(filepath, "w") as f:
        f.write(content)
    print(f"Newsletter saved: {filepath}")
    return filepath
