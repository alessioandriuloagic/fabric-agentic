# GitHub Issue Attachments and GitHub App Installation Tokens

**Research date:** 2026-08-25  
**Source policy:** GitHub Docs and GitHub REST API documentation only. No attachment content, customer transcript, access token, or token-derived value was collected or stored.

## Executive conclusion

GitHub's documented REST API exposes the issue or issue-comment resource, including its Markdown body, but it does not document a REST endpoint that resolves or downloads a file referenced by a `github.com/user-attachments/assets/...` or `github.com/user-attachments/files/...` link. The documented repository Contents API is for files that are actually in a repository path; it is not an API for issue attachments. Sources: [Get an issue](https://docs.github.com/en/rest/issues/issues#get-an-issue), [Get an issue comment](https://docs.github.com/en/rest/issues/comments#get-an-issue-comment), [Get repository content](https://docs.github.com/en/rest/repos/contents#get-repository-content).

Therefore, an installation token successfully reading the issue does not establish that it can fetch the linked attachment. The most likely explanation for this project's `404` is an authorization boundary at the attachment URL or its redirect target, rather than a missing issue. GitHub explicitly says that requests for private resources can return `404` when authentication, app permissions, installation ownership, repository access, or token validity is insufficient. Sources: [Troubleshooting the REST API: 404 for an existing resource](https://docs.github.com/en/rest/using-the-rest-api/troubleshooting-the-rest-api#404-not-found-for-an-existing-resource), [Authenticating to the REST API](https://docs.github.com/en/rest/authentication/authenticating-to-the-rest-api).

## What GitHub documents

### Attachment links are content in an issue body or comment

GitHub's issue REST response includes `body`, `body_text`, and `body_html`; the issue-comment response likewise includes `body`, `body_text`, and `body_html`. The webhook documentation models an issue-comment event as a `comment` object and an issue event as an `issue` object. These are the documented API resources from which an integration can obtain the Markdown containing an attachment link. Sources: [Get an issue](https://docs.github.com/en/rest/issues/issues#get-an-issue), [Get an issue comment](https://docs.github.com/en/rest/issues/comments#get-an-issue-comment), [Issue comment webhook](https://docs.github.com/en/webhooks/webhook-events-and-payloads#issue_comment), [Issues webhook](https://docs.github.com/en/webhooks/webhook-events-and-payloads#issues).

The REST issue and issue-comment references list endpoints for managing the issue/comment resources, but do not list a user-attachments asset/file download endpoint. This is an observation about the published GitHub REST reference, not a claim that GitHub's internal attachment service has no implementation. Sources: [REST API endpoints for issues](https://docs.github.com/en/rest/issues/issues), [REST API endpoints for issue comments](https://docs.github.com/en/rest/issues/comments).

### Repository Contents is a different resource model

`GET /repos/{owner}/{repo}/contents/{path}` gets a file or directory at a repository path. For a repository file, GitHub documents `download_url`, and says that the endpoint's download URLs are temporary and should be freshly obtained from the Contents API. An issue attachment URL is not a repository path and does not produce a Contents API object. Sources: [Get repository content](https://docs.github.com/en/rest/repos/contents#get-repository-content).

Do not transform a `user-attachments` URL into `/repos/{owner}/{repo}/contents/...`; that would be a different URL and resource. GitHub also advises integrations not to manually parse or predict URL structures returned by the API. Source: [REST API best practices: Do not manually parse URLs](https://docs.github.com/en/rest/using-the-rest-api/best-practices-for-using-the-rest-api#do-not-manually-parse-urls).

### Redirects are part of the documented REST behavior

GitHub says REST requests may redirect, and clients should follow the `Location` URL. `301` is permanent; `302` and `307` are temporary. The Contents API documents `302` for archive downloads and asks clients to follow the redirect. Sources: [REST API best practices: Follow redirects](https://docs.github.com/en/rest/using-the-rest-api/best-practices-for-using-the-rest-api#follow-redirects), [Download a repository archive](https://docs.github.com/en/rest/repos/contents#download-a-repository-archive-zip).

The documentation does not state that an `Authorization` header is accepted by, or should be forwarded to, an attachment host after a redirect. Consequently, a client must inspect redirect behavior without logging the `Location` query string or credentials, and must follow the target only according to its HTTP client's documented credential-forwarding rules. This is an implementation caution, not a GitHub promise about attachment-host authentication. Source for the redirect requirement: [Follow redirects](https://docs.github.com/en/rest/using-the-rest-api/best-practices-for-using-the-rest-api#follow-redirects).

### Installation access tokens are scoped to an installation

GitHub documents that an installation token can access resources owned by the account where the app is installed, provided the app has the necessary repository access and permissions. When the token is created, its repository set can be limited further; it cannot be expanded beyond repositories granted to the installation. If no narrower permission set is requested, it receives the permissions granted to the app. Installation tokens expire after one hour. Sources: [Authenticating as a GitHub App installation](https://docs.github.com/en/apps/creating-github-apps/authenticating-with-a-github-app/authenticating-as-a-github-app-installation), [Create an installation access token](https://docs.github.com/en/rest/apps/installations#create-an-installation-access-token-for-an-app).

The installation endpoint `GET /installation/repositories` lists the repositories accessible to the installation. The installation object also exposes `repository_selection` and granted permissions. Source: [List repositories accessible to the app installation](https://docs.github.com/en/rest/apps/installations#list-repositories-accessible-to-the-app-installation).

### Relevant repository permissions

| Permission | What the official REST permission matrix documents | Relevance |
| --- | --- | --- |
| `Issues: read` | Includes `GET /repos/{owner}/{repo}/issues/{issue_number}` and issue-comment read endpoints. | Needed to read the issue/comment body that contains the link. |
| `Contents: read` | Includes `GET /repos/{owner}/{repo}/contents/{path}` and repository Git/content reads. | Needed for repository files; no documented mapping to issue attachments. |
| `Metadata: read` | Includes repository metadata endpoints such as `GET /repos/{owner}/{repo}`. | Repository discovery/metadata; not documented as an attachment-download permission. |

Sources for all rows: [Permissions required for GitHub Apps](https://docs.github.com/en/rest/authentication/permissions-required-for-github-apps), [Get an issue](https://docs.github.com/en/rest/issues/issues#get-an-issue), [Get repository content](https://docs.github.com/en/rest/repos/contents#get-repository-content).

GitHub says the endpoint reference is authoritative for whether an endpoint works with GitHub Apps and which permissions it requires. It also says insufficient permissions normally produce `403` for a REST API request, while the troubleshooting guidance explains that existing private resources can instead appear as `404` in several authorization cases. Sources: [Choosing permissions for a GitHub App](https://docs.github.com/en/apps/creating-github-apps/registering-a-github-app/choosing-permissions-for-a-github-app#choosing-permissions-for-rest-api-access), [404 for an existing resource](https://docs.github.com/en/rest/using-the-rest-api/troubleshooting-the-rest-api#404-not-found-for-an-existing-resource).

## Can a GitHub App access attachments uploaded by users?

The official documentation supports this narrower conclusion: a GitHub App can receive issue and issue-comment events, and can read the corresponding issue/comment through documented endpoints when it has the required `Issues` permission and installation access. The webhook payload includes the issue/comment resource, not a separate documented attachment object or attachment API. Sources: [Issue comment webhook](https://docs.github.com/en/webhooks/webhook-events-and-payloads#issue_comment), [Issues webhook](https://docs.github.com/en/webhooks/webhook-events-and-payloads#issues), [Permissions required for GitHub Apps](https://docs.github.com/en/rest/authentication/permissions-required-for-github-apps).

GitHub's public Docs and REST references consulted here do not promise that an installation token can download every attachment uploaded by any user merely because the app can read the issue. They also do not document a separate permission named “issue attachments.” Thus the answer is: the app may read the link as issue content, but direct attachment retrieval is not guaranteed by the documented GitHub App permission contract. Whether a particular attachment URL is accessible depends on the attachment service's access decision, the installation/repository context, and the URL's current validity; the last two are documented checks, while the attachment-service decision is not publicly specified in these references.

## Diagnosis of this project's observed behavior

**Observation:** the installation token can read the issue, but an HTTP request to an attachment URL returns `404`.

**Most likely diagnosis:** the two requests are evaluated by different resource surfaces. `GET /repos/.../issues/...` is a documented REST endpoint governed by the repository's `Issues` permission. `https://github.com/user-attachments/...` is not a documented REST endpoint and may redirect or apply access rules outside the issue endpoint. GitHub specifically lists missing app permissions, missing installation repository access, wrong installation owner/account, expired or revoked installation tokens, and incorrect URLs as reasons to investigate when an existing resource returns `404`. Sources: [Get an issue](https://docs.github.com/en/rest/issues/issues#get-an-issue), [404 for an existing resource](https://docs.github.com/en/rest/using-the-rest-api/troubleshooting-the-rest-api#404-not-found-for-an-existing-resource), [Installation authentication](https://docs.github.com/en/apps/creating-github-apps/authenticating-with-a-github-app/authenticating-as-a-github-app-installation).

**Important non-diagnosis:** adding `Contents: read` alone is not supported by the official docs as a fix for `user-attachments` URLs. `Contents: read` is the documented permission for repository content endpoints; no attachment endpoint or required attachment permission is published in the permission matrix. Source: [Permissions required for GitHub Apps](https://docs.github.com/en/rest/authentication/permissions-required-for-github-apps).

## Actionable recommendations

1. **Keep the two stages separate.** Read issue bodies and comments through the Issues API and extract links as untrusted external URLs. Do not treat an attachment link as a repository-content URL. Sources: [Get an issue](https://docs.github.com/en/rest/issues/issues#get-an-issue), [Get an issue comment](https://docs.github.com/en/rest/issues/comments#get-an-issue-comment), [Get repository content](https://docs.github.com/en/rest/repos/contents#get-repository-content).
2. **Verify installation scope without exposing secrets.** In a controlled run, compare the target repository with `GET /installation/repositories`; inspect only status codes, response headers, and redacted host/path metadata. Confirm the app is installed on the account that owns the repository and that the installation selection includes the repository. Sources: [List repositories accessible to the app installation](https://docs.github.com/en/rest/apps/installations#list-repositories-accessible-to-the-app-installation), [404 troubleshooting](https://docs.github.com/en/rest/using-the-rest-api/troubleshooting-the-rest-api#404-not-found-for-an-existing-resource).
3. **Verify effective token properties at creation time.** Confirm, in memory only, the installation token's expiry, repository restriction, and effective permission set. Refresh after one hour or on revocation; never write the token or full response to logs. Source: [Authenticating as a GitHub App installation](https://docs.github.com/en/apps/creating-github-apps/authenticating-with-a-github-app/authenticating-as-a-github-app-installation).
4. **Follow redirects, but test the target independently.** Record only the status code, redirect count, final host, and safe path shape. Do not assume that a bearer header intended for `api.github.com` is valid for a redirected attachment host; the official docs require following redirects but do not define attachment-host credential forwarding. Source: [Follow redirects](https://docs.github.com/en/rest/using-the-rest-api/best-practices-for-using-the-rest-api#follow-redirects).
5. **Check response headers before changing permissions.** For a REST endpoint returning a permission error, `X-Accepted-GitHub-Permissions` identifies required permissions. If the attachment request is not a documented REST endpoint or does not return that header, treat that as evidence that the permission matrix cannot diagnose it directly. Source: [Resource not accessible](https://docs.github.com/en/rest/using-the-rest-api/troubleshooting-the-rest-api#resource-not-accessible).
6. **Use a first-class storage path when automation must process files.** For durable machine-to-machine ingestion, store the file in repository contents, a release asset, or an approved external object store and pass the resulting documented API/object identity to the app. This avoids depending on an undocumented attachment-download contract. The repository Contents API and release-asset APIs are documented separately from issue bodies. Sources: [Get repository content](https://docs.github.com/en/rest/repos/contents#get-repository-content), [Release assets](https://docs.github.com/en/rest/releases/assets).

## Source inventory

- [GitHub Docs: Choosing permissions for a GitHub App](https://docs.github.com/en/apps/creating-github-apps/registering-a-github-app/choosing-permissions-for-a-github-app)
- [REST: Get an issue](https://docs.github.com/en/rest/issues/issues#get-an-issue)
- [REST: Get an issue comment](https://docs.github.com/en/rest/issues/comments#get-an-issue-comment)
- [REST: Get repository content](https://docs.github.com/en/rest/repos/contents#get-repository-content)
- [REST: Create an installation access token](https://docs.github.com/en/rest/apps/installations#create-an-installation-access-token-for-an-app)
- [REST: List repositories accessible to the app installation](https://docs.github.com/en/rest/apps/installations#list-repositories-accessible-to-the-app-installation)
- [REST: Permissions required for GitHub Apps](https://docs.github.com/en/rest/authentication/permissions-required-for-github-apps)
- [REST: Authenticate to the REST API](https://docs.github.com/en/rest/authentication/authenticating-to-the-rest-api)
- [REST: Authenticate as a GitHub App installation](https://docs.github.com/en/apps/creating-github-apps/authenticating-with-a-github-app/authenticating-as-a-github-app-installation)
- [REST: Troubleshoot the REST API](https://docs.github.com/en/rest/using-the-rest-api/troubleshooting-the-rest-api)
- [REST: Best practices for using the REST API](https://docs.github.com/en/rest/using-the-rest-api/best-practices-for-using-the-rest-api)
- [Webhooks: Issues](https://docs.github.com/en/webhooks/webhook-events-and-payloads#issues)
- [Webhooks: Issue comment](https://docs.github.com/en/webhooks/webhook-events-and-payloads#issue_comment)