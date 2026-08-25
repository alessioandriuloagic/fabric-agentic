# Dev Dispatcher Task Contract

The deterministic dispatcher starts a fresh Dev Agent session with a JSON task record. The record
contains routing metadata only; the work item and repository remain authoritative.

```json
{
  "work_item_id": 42,
  "trigger": "new_work",
  "work_item_url": "https://dev.azure.com/<organization>/<project>/_workitems/edit/42",
  "repository_path": "C:/agents/dev/fabric-agentic",
  "pull_request_url": null,
  "issue_context_path": "C:/agents/dev/tasks/work-item-42/issue-context.md"
}
```

| Field | Required | Meaning |
|---|---|---|
| `work_item_id` | Yes | Positive Azure Boards work item identifier. |
| `trigger` | Yes | `new_work`, `human_reply`, or `review_thread`. |
| `work_item_url` | Yes | Canonical tracker reference. |
| `repository_path` | Yes | Isolated Dev Agent clone. |
| `pull_request_url` | For review trigger | PR containing the unresolved review thread. |
| `issue_context_path` | Optional | Local file containing issue body and staged, allowlisted attachments. |

The dispatcher stores task records and session logs outside the repository. They must not contain
tokens, credentials, raw data, or copied environment-variable values.