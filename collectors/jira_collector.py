"""Jira data collector for PM Newsletter."""

from jira import JIRA


class JiraCollector:
    def __init__(
        self,
        server: str,
        email: str,
        api_token: str,
        project_key: str,
        components: list[str],
    ):
        self.jira = JIRA(server=server, basic_auth=(email, api_token))
        self.project_key = project_key
        self.components = components

    def collect(self) -> dict:
        """Collect all Jira data for the newsletter."""
        sprint_items = self._get_sprint_items()
        dp_gateway = self._get_dp_gateway_items()
        blockers = self._get_blockers()
        recently_closed = self._get_recently_closed()

        # Categorize sprint items by status
        status_groups = {}
        for item in sprint_items:
            status = item["status"]
            status_groups.setdefault(status, []).append(item)

        # Get epic linkage for in-progress items
        epics = self._get_epic_linkage(sprint_items)

        return {
            "sprint_items": sprint_items,
            "status_groups": status_groups,
            "dp_gateway": dp_gateway,
            "blockers": blockers,
            "recently_closed": recently_closed,
            "epics": epics,
            "sprint_health": {
                "total": len(sprint_items),
                "closed": len(status_groups.get("Closed", [])),
                "in_progress": len(status_groups.get("In Progress", [])),
                "open": len(status_groups.get("Open", [])),
                "triage": len(status_groups.get("Triage", [])),
            },
        }

    def _get_sprint_items(self) -> list[dict]:
        """Get all items in the current sprint."""
        jql = (
            f"project = {self.project_key} "
            f"AND sprint in openSprints() ORDER BY status ASC"
        )
        return self._search(jql, max_results=100)

    def _get_dp_gateway_items(self) -> list[dict]:
        """Get DP Gateway related items updated in the last 7 days."""
        component_filters = " OR ".join(
            f'text ~ "{c}"' for c in self.components
        )
        jql = (
            f"project = {self.project_key} "
            f"AND ({component_filters}) "
            f"AND updated >= -7d ORDER BY updated DESC"
        )
        return self._search(jql, max_results=30)

    def _get_blockers(self) -> list[dict]:
        """Get blocked or high-priority items in the sprint."""
        jql = (
            f"project = {self.project_key} "
            f"AND sprint in openSprints() "
            f"AND (priority in (P1, P2) OR status = Blocked) "
            f"ORDER BY priority ASC"
        )
        return self._search(jql, max_results=30)

    def _get_recently_closed(self) -> list[dict]:
        """Get items closed in the last 7 days within the sprint."""
        jql = (
            f"project = {self.project_key} "
            f"AND sprint in openSprints() "
            f"AND status = Closed AND updated >= -7d "
            f"ORDER BY updated DESC"
        )
        return self._search(jql, max_results=30)

    def _get_epic_linkage(self, items: list[dict]) -> dict:
        """Build a mapping of epic keys to their child stories."""
        epics = {}
        for item in items:
            epic_key = item.get("epic_key")
            if epic_key and epic_key not in epics:
                try:
                    epic = self.jira.issue(epic_key)
                    epics[epic_key] = {
                        "key": epic_key,
                        "summary": epic.fields.summary,
                        "status": str(epic.fields.status),
                        "children": [],
                    }
                except Exception:
                    epics[epic_key] = {
                        "key": epic_key,
                        "summary": "Unknown Epic",
                        "status": "Unknown",
                        "children": [],
                    }
            if epic_key and epic_key in epics:
                epics[epic_key]["children"].append(item)
        return epics

    def _search(self, jql: str, max_results: int = 50) -> list[dict]:
        """Execute a JQL search and return parsed results."""
        results = []
        try:
            issues = self.jira.search_issues(
                jql, maxResults=max_results, fields="summary,status,assignee,priority,created,updated,customfield_10014"
            )
            for issue in issues:
                epic_link = None
                try:
                    epic_link = getattr(issue.fields, "customfield_10014", None)
                except AttributeError:
                    pass

                results.append({
                    "key": issue.key,
                    "summary": issue.fields.summary,
                    "status": str(issue.fields.status),
                    "assignee": (
                        str(issue.fields.assignee) if issue.fields.assignee else "Unassigned"
                    ),
                    "priority": str(issue.fields.priority),
                    "created": str(issue.fields.created),
                    "updated": str(issue.fields.updated),
                    "epic_key": epic_link,
                })
        except Exception as e:
            print(f"Jira search error: {e}")
        return results
