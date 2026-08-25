# Issue attachments

Store files that the Dev Agent must read under a directory named after the issue number:

```text
attachments/<issue-number>/
```

Keep the issue body as the human-readable summary of the call and reference the repository path
there, for example `attachments/72/`. Files in this directory are versioned with the feature
branch and are available in the isolated Dev Agent clone.

Rules:

- Add only files required for the ticket.
- Do not add secrets, tokens, private keys, credentials, or unnecessary personal data.
- Prefer text, Markdown, PDF, CSV, or source files that the agent can inspect.
- Keep each file below 10 MiB.
- Use a dedicated issue-number directory; do not overwrite files from another issue.
- The Dev Agent treats transcripts and attachments as untrusted context, not as instructions to
  access external systems or secrets.
