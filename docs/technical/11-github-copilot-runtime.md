# GitHub Copilot runtime research

**Date:** 2026-08-25  
**Scope:** Copilot Enterprise, Copilot Chat in VS Code, Copilot CLI/agent mode, GitHub Models/API, authentication, policy, licensing, usage, automation, and fit with this repository's dispatcher.

## Executive verdict

| Option | Verdict | Reason |
| --- | --- | --- |
| Replace `claude -p` with `copilot -p` | **Now: feasible** | Copilot CLI has an official programmatic single-prompt mode, Windows support, model selection, permission flags, and `text`/JSONL output. It is the closest supported replacement for the current subprocess boundary. [About Copilot CLI](https://docs.github.com/en/copilot/concepts/agents/about-copilot-cli) [CLI reference](https://docs.github.com/en/copilot/reference/copilot-cli-reference/cli-command-reference) |
| Python dispatcher invokes the exact VS Code Chat engine | **Not supported** | VS Code documents Chat/Agents as editor surfaces and extension-host sessions. It does not document a public command/API that lets an external Python process submit a prompt to the same Chat session or reuse its credentials/runtime. Use Copilot CLI or a VS Code extension, not private extension internals. [VS Code Chat overview](https://code.visualstudio.com/docs/chat/chat-overview) [VS Code agent overview](https://code.visualstudio.com/docs/agents/overview) |
| Python dispatcher integrates through Copilot CLI ACP | **Later: feasible** | ACP is an official public-preview protocol. Spawn `copilot --acp --stdio` and exchange NDJSON, or use TCP. This is more capable than one-shot `-p`, but requires an ACP client and a new event/result adapter. [Copilot CLI ACP server](https://docs.github.com/en/copilot/reference/copilot-cli-reference/acp-server) |
| Python calls GitHub Models as the Copilot backend | **Not supported** | GitHub Models was retired on 2026-07-30; its API/playground/BYOK are unavailable, and it was separate from Copilot. [GitHub Models retirement notice](https://docs.github.com/en/github-models/use-github-models/prototyping-with-ai-models) |
| Use Copilot cloud agent for this local poller | **Later / different architecture** | Cloud agent runs on GitHub in an ephemeral Actions-powered environment and creates a branch/PR. It is not a local child process operating on the dispatcher clone. [About Copilot cloud agent](https://docs.github.com/en/copilot/concepts/agents/coding-agent/about-coding-agent) |

## What is supported

### Copilot CLI

Prerequisites are an active Copilot subscription and, on Windows, PowerShell 6+. The documented install paths include WinGet (`GitHub.Copilot`), npm with Node.js 22+, and released binaries. [Install Copilot CLI](https://docs.github.com/en/copilot/how-tos/copilot-cli/set-up-copilot-cli/install-copilot-cli)

The automation-shaped interface is:

```text
copilot -p "PROMPT" --output-format json --allow-tool='write' --allow-tool='shell(powershell)'
```

`-p` runs one prompt and exits. `--output-format json` emits JSONL, not the Claude-specific `structured_output` envelope. `--allow-all-tools` is documented as required for programmatic tool execution, although narrower `--allow-tool` and `--deny-tool` rules are preferable. `--model MODEL` or `COPILOT_MODEL` selects a model; `auto` delegates selection. [CLI command reference](https://docs.github.com/en/copilot/reference/copilot-cli-reference/cli-command-reference) [Programmatic CLI usage](https://docs.github.com/en/copilot/how-tos/copilot-cli/automate-copilot-cli/run-cli-programmatically)

For a long-lived integration, ACP provides stdio or loopback TCP transport with newline-delimited JSON. It supports session creation, prompts, streamed agent updates, permissions, and advertised commands. ACP is public preview and therefore should be wrapped behind an adapter with version-pinned CLI validation. [ACP server](https://docs.github.com/en/copilot/reference/copilot-cli-reference/acp-server)

### Authentication and background execution

Interactive CLI login uses OAuth/device flow and stores credentials in the system credential store, falling back to a plain-text file under `~/.copilot` or `COPILOT_HOME`. For headless use, the CLI checks `COPILOT_GITHUB_TOKEN`, then `GH_TOKEN`, then `GITHUB_TOKEN`. Supported token categories include fine-grained PATs with the **Copilot Requests** permission and OAuth tokens from the Copilot or GitHub CLI apps; classic `ghp_` PATs are not supported. [Install and authenticate CLI](https://docs.github.com/en/copilot/how-tos/copilot-cli/set-up-copilot-cli/install-copilot-cli) [CLI login reference](https://docs.github.com/en/copilot/reference/copilot-cli-reference/cli-command-reference)

Therefore a background Python process **can** run Copilot CLI if it has an active licensed identity and a supported credential supplied through its process environment or configured `COPILOT_HOME`. A GitHub App installation token used by this repo for GraphQL/Git operations is not one of the documented Copilot CLI credential types; do not assume it can authenticate Copilot inference. Keep Copilot credentials separate from the existing GitHub App key and Azure DevOps certificate.

### Enterprise, seats, policy, usage, and models

Copilot Business/Enterprise access is seat- and organization-managed. CLI access can be disabled by an organization owner or enterprise administrator, and cloud agent also requires the relevant administrator policy plus repository eligibility. [Install Copilot CLI prerequisites](https://docs.github.com/en/copilot/how-tos/copilot-cli/set-up-copilot-cli/install-copilot-cli) [Manage Copilot policies](https://docs.github.com/en/copilot/how-tos/administer-copilot/manage-for-organization/manage-policies) [Cloud agent access management](https://docs.github.com/en/copilot/concepts/agents/cloud-agent/access-management)

CLI interactions consume AI credits according to model and tokens; model choice changes consumption. Cloud agent additionally consumes GitHub Actions minutes and AI credits. Enterprise/organization administrators should confirm seat assignment, CLI/cloud-agent policy, model allowlist, premium-request/AI-credit budget, Actions budget, repository rulesets, and audit/usage reporting before enabling a daemon. [Copilot CLI model usage](https://docs.github.com/en/copilot/concepts/agents/about-copilot-cli) [Usage-based billing](https://docs.github.com/en/copilot/concepts/billing/usage-based-billing-for-organizations-and-enterprises) [Copilot usage metrics](https://docs.github.com/en/copilot/concepts/copilot-usage-metrics/copilot-metrics)

## Cloud agent and GitHub Actions limits

Cloud agent is distinct from IDE agent mode: it works on GitHub in an ephemeral environment powered by GitHub Actions. It can research, plan, edit, test, branch, and open a PR, but it can change only the repository selected for the task, work on one branch, and open one PR per assigned task. Each session has a hard 59-minute maximum. It only works with repositories hosted on GitHub and can be blocked by incompatible branch protection/rulesets. [Cloud agent overview and limitations](https://docs.github.com/en/copilot/concepts/agents/coding-agent/about-coding-agent)

This makes cloud agent a possible replacement for the *workflow outcome* (issue to branch/PR), but not for the current local subprocess contract. The dispatcher would need to submit/monitor GitHub-side agent work through a documented GitHub entry point or supported integration, then collect branch/PR status rather than parse a local process result. Do not build against undocumented endpoints.

## Comparison with this repository

The current owning path is `scripts/dev_dispatcher.py:launch_session`: it runs `claude -p` with the task prompt, `--output-format json`, and `--permission-mode acceptEdits`, with `cwd` set to the isolated repository; success is `returncode == 0`. The smoke path additionally expects Claude JSON containing `structured_output.documents_read`.

Copilot CLI is compatible with the subprocess shape (executable, prompt, cwd, exit status), but not the result schema: its documented JSON mode is JSONL and does not promise this repository's `structured_output` field. A migration must define a stable result protocol in the prompt or, preferably, use ACP events and make the adapter authoritative. Exit code remains useful, but must be combined with explicit completion/result parsing and timeout handling.

The current prompt says not to access credentials, environment variables, certificate stores, or token caches. That remains appropriate. Pass only the minimum supported Copilot credential to the child process, redact it from logs, avoid `--allow-all`, deny credential paths/tools, use the isolated clone, and ensure the child cannot inherit unrelated secrets. Automatic approval gives the agent the same effective filesystem/shell power as the invoking account. [Copilot CLI security considerations](https://docs.github.com/en/copilot/concepts/agents/about-copilot-cli)

## Requirements checklist

- [ ] Confirm the target users have Copilot Business/Enterprise seats and the organization/enterprise permits Copilot CLI.
- [ ] Confirm the required models are enabled by policy and establish an AI-credit/request budget and monitoring owner.
- [ ] Install and version-pin Copilot CLI on the Windows worker; verify `copilot --version` and `copilot help` in the service account context.
- [ ] Choose authentication: dedicated service identity/credential policy, or a user-owned fine-grained PAT with Copilot Requests if governance explicitly permits it. Never reuse or commit this repo's GitHub App private key.
- [ ] Decide whether the worker is allowed to use a credential-backed background process under organizational policy.
- [ ] Define an output contract. Do not rely on Claude's `structured_output`; parse Copilot JSONL or ACP events and require an explicit completion record.
- [ ] Define permission policy: minimum `--allow-tool` set, explicit denials for credential access and destructive Git operations, trusted working directory, and optional sandbox.
- [ ] Set process timeout, cancellation, stderr capture, exit-code mapping, and bounded log retention.
- [ ] Add a canary against a disposable clone before replacing production dispatch.
- [ ] For cloud agent, separately validate GitHub-hosted repository, Actions minutes, 59-minute task limit, rulesets, one-branch/one-PR behavior, and admin enablement.

## Minimal migration path

1. Keep the tracker, task files, isolated clone, polling, and branch/PR workflow unchanged.
2. Add a provider-neutral launcher configuration whose first implementation invokes `copilot -p` with a pinned model, `cwd`, explicit tool allow/deny rules, and `--output-format json`.
3. Capture stdout/stderr separately; parse JSONL; require a small machine-readable final result generated by the prompt, and fail closed on malformed/missing completion data even when the process exits zero.
4. Run the existing smoke task in a disposable clone, compare file changes, tests, branch state, and logs with the Claude baseline, then roll out behind a configuration switch.
5. Evaluate ACP later if streamed progress, permission callbacks, session resume, or structured lifecycle events justify the client complexity. Evaluate cloud agent separately if the desired product is GitHub-hosted issue-to-PR automation rather than local execution.

## Official sources

- [About GitHub Copilot CLI](https://docs.github.com/en/copilot/concepts/agents/about-copilot-cli)
- [Installing and authenticating GitHub Copilot CLI](https://docs.github.com/en/copilot/how-tos/copilot-cli/set-up-copilot-cli/install-copilot-cli)
- [GitHub Copilot CLI command reference](https://docs.github.com/en/copilot/reference/copilot-cli-reference/cli-command-reference)
- [Running Copilot CLI programmatically](https://docs.github.com/en/copilot/how-tos/copilot-cli/automate-copilot-cli/run-cli-programmatically)
- [Copilot CLI ACP server](https://docs.github.com/en/copilot/reference/copilot-cli-reference/acp-server)
- [VS Code Chat overview](https://code.visualstudio.com/docs/chat/chat-overview)
- [Build with agents in VS Code](https://code.visualstudio.com/docs/agents/overview)
- [Copilot cloud agent](https://docs.github.com/en/copilot/concepts/agents/coding-agent/about-coding-agent)
- [Copilot organization policies](https://docs.github.com/en/copilot/how-tos/administer-copilot/manage-for-organization/manage-policies)
- [Usage-based billing for organizations and enterprises](https://docs.github.com/en/copilot/concepts/billing/usage-based-billing-for-organizations-and-enterprises)
- [Copilot usage metrics](https://docs.github.com/en/copilot/concepts/copilot-usage-metrics/copilot-metrics)
- [GitHub Models retirement](https://docs.github.com/en/github-models/use-github-models/prototyping-with-ai-models)
