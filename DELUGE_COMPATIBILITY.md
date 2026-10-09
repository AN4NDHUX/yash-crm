# Deluge compatibility and safety contract

The CRM implements a **bounded Deluge-inspired workflow subset**, not a general Zoho-hosted Deluge interpreter. Do not advertise complete Zoho Deluge compatibility.

## Executable functionality
- CRM record field updates, tags, tasks, notifications, and audit events.
- Nested `if` conditions with limited comparisons and compound boolean expressions.
- Bounded literal string-list `for each` loops with nesting depth and action-budget limits.
- Bounded structured programs: local variable assignment/reassignment, List/Map local mutation, `if / else if / else`, `for each` over local collections, `while`, `break`, `continue`, and `return`, with 200-operation and 20-CRM-action ceilings. Existing restricted single-line scripts remain compatible.
- Explicit expression arguments prefixed by `=` for arithmetic, comparison, boolean operators, current-record references, and a limited subset of Map/List functions.
- Read-only Map/List methods `get`, `size`, `contains`, `containsKey`, `isEmpty`, `keys`, `values`, `toString`.
- Bounded ephemeral Map/List `put`, `add`, and `remove`. Mutating record-backed collections in expression evaluation is prohibited.
- Local workspace CRM task adapters: `zoho.crm.v8.getRecordById`, `getRecords`, `searchRecords`, `createRecord`, `updateRecord`, and `deleteRecord` on allowed modules, with organization, membership, profile, field and record-access checks. These tasks operate on CONVOSIS data, not Zoho-hosted data.
- Legacy current-record `zoho.crm.updateRecord(..., $record.id, ...)` and `zoho.crm.v8.updateRecord` syntax remains supported.
- `invokeurl(...)` legacy calls continue to queue the configured, signed webhook. Structured bracketed `invokeurl [url: ..., type: ..., connection: ..., body: ...]` now queues an organization-scoped HTTPS worker request, using OAuth2 refresh/client-credentials grants or administrator-configured API keys.
- Structured `invokeurl` returns a queue receipt, not a synchronous remote HTTP response. Provider credentials must be configured by an administrator outside the script.

## Not yet supported
- User-defined function declarations/invocation, exception handling, switch statements, unrestricted dynamic loops, complex nested Deluge task expressions, unrestricted nested Map/List mutation, full date/math/string functions and exact Zoho type coercion/return semantics. Structured blocks accept opening braces on the header line or the following line.
- Full Zoho invokeurl parity (synchronous remote responses, all options, files and multipart) and interactive OAuth consent / connection lifecycle. A worker-managed, connection-scoped subset is available.
- Complete Zoho CRM task parity: advanced criteria, related records, upsert, lead conversion, inventory tasks, attachments, Zoho API request options, and Zoho-specific response/error semantics.
- Provider-specific interactive connection management, token rotation/persistence, and exhaustive external API scopes and subscription entitlement rules.

## Production requirements
- The separate worker must be deployed to use outbound integrations.
- Configure `WORKFLOW_WEBHOOK_URL` as a trusted HTTPS endpoint and a secret of at least 32 characters in `WORKFLOW_WEBHOOK_SECRET`.
- The worker blocks redirects, uses a finite timeout, signs payloads and retries with idempotency keys.
- Validation and runtime execution fail closed for unsupported syntax and protected CRM identifiers.
- Full Deluge parity requires a dedicated interpreter, authorization-aware CRM task layer, connections/credential store, compliance tests against the reference language and documented version compatibility.
