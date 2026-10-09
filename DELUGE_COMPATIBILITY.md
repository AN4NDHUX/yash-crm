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
- `zoho.crm.updateRecord("Leads", $record.id, {"status":"Qualified"})` for **current-record-only** updates with current-module verification and protected-field enforcement. This is not a cross-record update API.
- `invokeurl("event payload")` or `crm.invokeUrl("event payload")` creates an outbound **queued webhook** to the administrator-configured `WORKFLOW_WEBHOOK_URL`, signed using `WORKFLOW_WEBHOOK_SECRET` and delivered by the separate workflow worker. These calls do **not** return HTTP responses, accept custom URL destinations, or behave like standard Zoho `invokeurl`.

## Not yet supported
- User-defined function declarations/invocation, exception handling, switch statements, unrestricted dynamic loops, complex nested Deluge task expressions, unrestricted nested Map/List mutation, full date/math/string functions and exact Zoho type coercion/return semantics. Structured blocks currently require header and opening brace on the same line.
- Standard multiline Zoho `invokeurl [url: ..., type: ..., connection: ...]` syntax, arbitrary methods, responses, headers and OAuth connections.
- Zoho CRM task parity including cross-record CRUD, searchRecords, getRecords, attachments, mail, inventory operations, transactional trigger handling, and Zoho-specific error/response semantics.
- Provider-specific connections, credential lifecycle, full tenant entitlement and API scope enforcement for outbound integrations.

## Production requirements
- The separate worker must be deployed to use outbound integrations.
- Configure `WORKFLOW_WEBHOOK_URL` as a trusted HTTPS endpoint and a secret of at least 32 characters in `WORKFLOW_WEBHOOK_SECRET`.
- The worker blocks redirects, uses a finite timeout, signs payloads and retries with idempotency keys.
- Validation and runtime execution fail closed for unsupported syntax and protected CRM identifiers.
- Full Deluge parity requires a dedicated interpreter, authorization-aware CRM task layer, connections/credential store, compliance tests against the reference language and documented version compatibility.
