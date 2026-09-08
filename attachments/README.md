# Issue attachments

Store files that the Dev Agent must read under a directory named after the issue number:

```text
attachments/<issue-number>/
```

For automatic dispatcher sessions, this directory must be committed and pushed to the remote branch
that the agent clone updates from. A file that exists only in the operator's local working copy is
not visible to Issue, Dev, or Review Agent sessions.

Keep the issue body as the human-readable summary of the call and reference the repository path
there, for example `attachments/72/`. Files in this directory are versioned with the feature
branch and are available in the isolated Dev Agent clone.

For an exploratory Issue Agent session inside VS Code/chat, local files or chat attachments can be
used as raw input. Before the automatic chain starts, summarize the material in the GitHub issue or
commit and push the required files under the issue-number directory.

Rules:

- Add only files required for the ticket.
- Do not add secrets, tokens, private keys, credentials, or unnecessary personal data.
- Prefer text, Markdown, PDF, CSV, or source files that the agent can inspect.
- Keep each file below 10 MiB.
- Use a dedicated issue-number directory; do not overwrite files from another issue.
- The Dev Agent treats transcripts and attachments as untrusted context, not as instructions to
  access external systems or secrets.
