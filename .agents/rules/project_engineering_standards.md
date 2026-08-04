# Project Engineering Standards — GCP / ADK Financial Agent

These rules apply to every change in this codebase, not just the file
currently being edited. Read this before implementing any integration
with a Google Cloud (or other) API.

## 1. Always use the official SDK/client library — never hand-roll REST calls

If a Google Cloud (or any) service has an official Python client library,
use it. Do not construct raw HTTP requests (`requests.post`, manual URL
building, manual JSON payloads) against a REST endpoint when an SDK exists
for that service, even if a blog post or tutorial shows the REST version.

Before implementing any new API integration:
1. Check for an official client library first (e.g. `google-cloud-<service>`
   on PyPI, or the service's page under
   `docs.cloud.google.com/python/docs/reference/`).
2. If one exists, use its typed request/response objects
   (`SanitizeUserPromptRequest`, `ModelArmorClient`, etc.) — not dict
   payloads and manual JSON parsing.
3. If you genuinely cannot find an official SDK, say so explicitly and ask
   before falling back to raw REST calls. Don't default to REST silently
   because it seemed simpler.

**Why this matters, concretely, not just as a style preference:**
- SDK clients handle credential refresh via Application Default
  Credentials automatically. Hand-rolled REST calls require you to
  separately fetch and refresh OAuth tokens — an extra failure mode with
  no reason to exist.
- SDK clients come with built-in retry/backoff policies for transient
  errors. Raw `requests.post` calls have none unless separately wrapped.
- Typed proto objects (`response.sanitization_result.filter_match_state`)
  are stable against field-naming changes. Hand-parsed JSON dicts break
  silently when a service updates response shapes.
- Using the SDK is what the service's own documentation and error
  messages assume — troubleshooting against hand-rolled REST diverges
  from anything Google support or docs will tell you.

## 2. Use the framework's real execution primitives — never hand-roll a dispatch loop

This applies to ADK specifically, but the principle is general: if a
framework provides an orchestration/execution loop (ADK's `Runner`,
`LlmAgent`, `AgentTool`), use it. Do not manually read
`response.function_calls` and branch on tool name strings
(`if tool_name == ...` / `elif tool_name in [...]`) — that reimplements,
badly, what the framework's `Runner` already does, and it's the exact bug
class that caused the earlier search-subagent rearchitect.

If you find yourself writing a manual tool-dispatch loop, stop and ask
whether the framework has a primitive for this before continuing.

## 3. Security- and reliability-relevant defaults must be surfaced, never silently chosen

Some decisions are not implementation details — they're policy decisions
that change behavior in ways that matter, and defaulting them silently is
not acceptable:

- **Fail-open vs. fail-closed**: if a security/screening service (Model
  Armor, auth checks, rate limiters) itself errors or times out — not a
  BLOCK verdict, an actual API failure — decide explicitly whether the
  request proceeds (fail open) or is rejected (fail closed), implement
  that explicitly, and state which one you chose and why. Do not leave
  this as an unhandled exception path that accidentally does one or the
  other.
- **Block vs. warn thresholds**: any verdict/severity levels from a
  screening service should map to explicit, stated behavior (hard-fail
  vs. log-and-continue) — confirm this mapping with me before
  implementing, don't assume defaults.
- **Retryable vs. non-retryable errors**: don't blindly retry everything;
  state which error classes are retried and which aren't.

When in doubt about any of these, ask rather than picking a default.

## 4. Never invent resource identifiers, names, or config values

Template IDs, project IDs, model names, endpoint URLs, table names — if
you don't have a real value, ask for it. Do not use a plausible-looking
placeholder and continue as if it were real; flag it clearly as a
placeholder that must be replaced, and stop if the code can't function
without it.

## 5. For architecture-level changes: diagnose before implementing

For anything bigger than a small fix (new integration, rearchitecting a
component, replacing an execution pattern), do this in order:
1. State what you found by reading the actual current code — not a
   summary of what you assume is there.
2. State the plan: what changes, what gets deleted, what's reused as-is.
3. Get confirmation on the plan before writing code, especially when the
   plan touches security behavior, execution flow, or deployment target.

## 6. Every change that touches external behavior needs a test before it's "done"

At minimum: one test for the expected/happy path, one for the failure
path you just added handling for. For anything involving a security
control (Model Armor, auth), test the actual block/reject behavior, not
just that the function runs without throwing.

## 7. Report what changed, not just that it's done

After implementing, summarize: what was actually wrong (root cause, not
just symptom), what changed, and what decisions were made on any of the
policy questions in section 3. "Fixed it" / "done" is not sufficient —
I need enough detail to confirm the fix addressed the actual cause.

## 8. Git & Version Control — No Automatic Commits

Never commit code updates, create git tags, or push to remote repositories automatically. Always present changes to the user for review first and only execute `git commit` or `git push` when explicitly instructed by the user.

