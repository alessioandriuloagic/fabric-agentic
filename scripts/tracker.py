"""Abstract work-item tracker interface and implementations."""

import json
import re
from abc import ABC, abstractmethod
from dataclasses import dataclass
from pathlib import Path
from typing import Callable
from urllib.request import Request, urlopen

from fabric_agentic.github_app_auth import create_installation_token


# GitHub GraphQL filters issues by any of the given labels, so the conjunction is enforced here.
WAITING_INPUT_LABELS = frozenset({"dev-agent", "waiting-input"})


class TrackerError(Exception):
    """Raised without including credentials or response bodies."""


@dataclass(frozen=True)
class WorkItem:
    """Normalized work item across trackers."""

    id: int | str  # int for Azure, str for GitHub (issue number)
    number: int  # sequential number for display
    state: str  # "To Do", "Doing", "Done" etc
    title: str
    tracker_type: str  # "azure_devops", "github_issues"


@dataclass(frozen=True)
class WorkItemComment:
    """Normalized comment across trackers."""

    id: int | str
    author: str
    text: str
    is_agent_comment: bool


class WorkItemTracker(ABC):
    """Abstract tracker interface for work-item lifecycle."""

    @abstractmethod
    def new_items(self) -> list[int | str]:
        """Return IDs of work items in 'To Do' state with dev-agent tag/label."""
        pass

    @abstractmethod
    def waiting_input_items(self) -> list[int | str]:
        """Return IDs of work items in 'Doing' state with waiting-input tag/label."""
        pass

    @abstractmethod
    def comments(self, item_id: int | str) -> list[WorkItemComment]:
        """Return all comments on a work item."""
        pass

    @abstractmethod
    def add_comment(self, item_id: int | str, text: str) -> None:
        """Add a comment to a work item."""
        pass

    @abstractmethod
    def set_state(self, item_id: int | str, state: str) -> None:
        """Transition a work item to a new state."""
        pass

    @abstractmethod
    def item_url(self, item_id: int | str) -> str:
        """Return the full URL to the work item."""
        pass

    def context(self, item_id: int | str) -> dict:
        """Return safe work-item context for the agent handoff."""
        return {"title": "", "body": "", "attachments": []}


class AzureDevOpsTracker(WorkItemTracker):
    """Azure Boards implementation of WorkItemTracker."""

    ADO_SCOPE = "https://app.vssps.visualstudio.com"

    def __init__(
        self,
        organization: str,
        project: str,
        token_provider: Callable[[], str],
        dev_agent_display_name: str = "[fabric-agentic-dev-agent]",
    ):
        self.organization = organization
        self.project = project
        self.token_provider = token_provider
        self.dev_agent_display_name = dev_agent_display_name

    def _request(self, method: str, path: str, body: dict | list | None = None) -> dict:
        token = self.token_provider()
        content_type = "application/json-patch+json" if isinstance(body, list) else "application/json"
        request = Request(
            f"https://dev.azure.com/{self.organization}/{self.project}{path}",
            data=json.dumps(body).encode("utf-8") if body is not None else None,
            method=method,
            headers={"Authorization": f"Bearer {token}", "Content-Type": content_type},
        )
        try:
            with urlopen(request) as response:
                return json.load(response)
        except Exception as error:
            raise TrackerError(f"Azure DevOps request failed: {method} {path}") from error

    def _work_item_ids(self, state: str, tags_filter: str) -> list[int]:
        query = {
            "query": f"SELECT [System.Id] FROM WorkItems WHERE [System.TeamProject] = @project AND [System.State] = '{state}' AND {tags_filter} ORDER BY [System.ChangedDate] ASC"
        }
        result = self._request("POST", "/_apis/wit/wiql?api-version=7.1", query)
        return [int(item["id"]) for item in result.get("workItems", [])]

    def new_items(self) -> list[int]:
        return self._work_item_ids("To Do", "[System.Tags] CONTAINS 'dev-agent'")

    def waiting_input_items(self) -> list[int]:
        return self._work_item_ids("Doing", "[System.Tags] CONTAINS 'dev-agent' AND [System.Tags] CONTAINS 'waiting-input'")

    def comments(self, item_id: int | str) -> list[WorkItemComment]:
        result = self._request("GET", f"/_apis/wit/workItems/{item_id}/comments?order=asc&api-version=7.1-preview.4")
        comments = []
        for comment in result.get("comments", []):
            comments.append(
                WorkItemComment(
                    id=int(comment["commentId"]),
                    author=comment.get("createdBy", {}).get("displayName", ""),
                    text=comment.get("content", ""),
                    is_agent_comment=comment.get("createdBy", {}).get("displayName", "") == self.dev_agent_display_name,
                )
            )
        return comments

    def add_comment(self, item_id: int | str, text: str) -> None:
        self._request("POST", f"/_apis/wit/workItems/{item_id}/comments?api-version=7.1-preview.4", {"text": text})

    def set_state(self, item_id: int | str, state: str) -> None:
        self._request("PATCH", f"/_apis/wit/workitems/{item_id}?api-version=7.1", [{"op": "add", "path": "/fields/System.State", "value": state}])

    def item_url(self, item_id: int | str) -> str:
        return f"https://dev.azure.com/{self.organization}/{self.project}/_workitems/edit/{item_id}"


class GitHubIssuesTracker(WorkItemTracker):
    """GitHub Issues implementation of WorkItemTracker."""

    def __init__(
        self,
        owner: str,
        repository: str,
        github_app_id: int,
        github_installation_id: int,
        github_private_key_path: Path,
        agent_identity: str = "[fabric-agentic-dev-agent]",
    ):
        self.owner = owner
        self.repository = repository
        self.github_app_id = github_app_id
        self.github_installation_id = github_installation_id
        self.github_private_key_path = github_private_key_path
        self.agent_identity = agent_identity

    def _token(self) -> str:
        return create_installation_token(
            self.github_app_id,
            self.github_installation_id,
            self.github_private_key_path,
        ).token

    def _graphql(self, query: str, variables: dict) -> dict:
        token = self._token()
        request = Request(
            "https://api.github.com/graphql",
            data=json.dumps({"query": query, "variables": variables}).encode("utf-8"),
            method="POST",
            headers={
                "Authorization": f"Bearer {token}",
                "Content-Type": "application/json",
                "X-GitHub-Api-Version": "2022-11-28",
            },
        )
        try:
            with urlopen(request) as response:
                result = json.load(response)
        except Exception as error:
            raise TrackerError(f"GitHub GraphQL request failed") from error
        if result.get("errors"):
            raise TrackerError(f"GitHub GraphQL error: {result['errors']}")
        return result["data"]

    def _rest(self, method: str, path: str, body: dict | None = None) -> dict:
        token = self._token()
        request = Request(
            f"https://api.github.com{path}",
            data=json.dumps(body).encode("utf-8") if body else None,
            method=method,
            headers={
                "Authorization": f"Bearer {token}",
                "Accept": "application/vnd.github.v3+json",
            },
        )
        try:
            with urlopen(request) as response:
                return json.load(response)
        except Exception as error:
            raise TrackerError(f"GitHub REST request failed: {method} {path}") from error

    def new_items(self) -> list[int]:
        """Return issue numbers with label 'dev-agent' in open state."""
        query = """
            query ($owner: String!, $repo: String!) {
              repository(owner: $owner, name: $repo) {
                issues(first: 100, states: OPEN, labels: "dev-agent", orderBy: {field: CREATED_AT, direction: ASC}) {
                  nodes {
                    number
                  }
                }
              }
            }
        """
        result = self._graphql(query, {"owner": self.owner, "repo": self.repository})
        return [issue["number"] for issue in result.get("repository", {}).get("issues", {}).get("nodes", [])]

    def waiting_input_items(self) -> list[int]:
        """Return issue numbers carrying both 'dev-agent' and 'waiting-input'."""
        query = """
            query ($owner: String!, $repo: String!) {
              repository(owner: $owner, name: $repo) {
                issues(first: 100, states: OPEN, labels: ["dev-agent", "waiting-input"], orderBy: {field: UPDATED_AT, direction: ASC}) {
                  nodes {
                    number
                    labels(first: 50) {
                      nodes {
                        name
                      }
                    }
                  }
                }
              }
            }
        """
        result = self._graphql(query, {"owner": self.owner, "repo": self.repository})
        waiting = []
        for issue in result.get("repository", {}).get("issues", {}).get("nodes", []):
            names = {label.get("name") for label in issue.get("labels", {}).get("nodes", [])}
            if WAITING_INPUT_LABELS <= names:
                waiting.append(issue["number"])
        return waiting

    def comments(self, item_id: int | str) -> list[WorkItemComment]:
        """Return all comments on an issue."""
        issue_number = int(item_id)
        result = self._rest("GET", f"/repos/{self.owner}/{self.repository}/issues/{issue_number}/comments")
        comments = []
        for comment in result if isinstance(result, list) else []:
            is_agent = self.agent_identity in comment.get("body", "")
            comments.append(
                WorkItemComment(
                    id=comment["id"],
                    author=comment.get("user", {}).get("login", ""),
                    text=comment.get("body", ""),
                    is_agent_comment=is_agent,
                )
            )
        return comments

    def context(self, item_id: int | str) -> dict:
        """Return issue body and allowlisted GitHub user-attachment URLs."""
        issue = self._rest("GET", f"/repos/{self.owner}/{self.repository}/issues/{int(item_id)}")
        body = issue.get("body") or ""
        attachments = sorted(set(re.findall(r"https://github\.com/user-attachments/[^)\s]+", body)))
        return {"title": issue.get("title", ""), "body": body, "attachments": attachments}

    def add_comment(self, item_id: int | str, text: str) -> None:
        """Add a comment to an issue."""
        issue_number = int(item_id)
        self._rest("POST", f"/repos/{self.owner}/{self.repository}/issues/{issue_number}/comments", {"body": text})

    def set_state(self, item_id: int | str, state: str) -> None:
        """Transition an issue to a new state (open/closed)."""
        issue_number = int(item_id)
        github_state = "closed" if state in ("Done", "Closed") else "open"
        self._rest("PATCH", f"/repos/{self.owner}/{self.repository}/issues/{issue_number}", {"state": github_state})

    def item_url(self, item_id: int | str) -> str:
        issue_number = int(item_id)
        return f"https://github.com/{self.owner}/{self.repository}/issues/{issue_number}"
