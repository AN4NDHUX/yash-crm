# CONVOSIS Deluge integrations (bounded runtime)

This is a permission-scoped Deluge-inspired runtime, not full Zoho Deluge compatibility.

## CRM record tasks
Supported methods: zoho.crm.v8.getRecordById, getRecords, searchRecords, createRecord, updateRecord and deleteRecord.
Legacy zoho.crm names are recognized for structured scripts.
Targets are local CONVOSIS CRM modules Leads, Contacts, Accounts, Deals and Products, NOT Zoho's hosted servers.
Caller must be an active organization member. Profile, record sharing and field permissions are enforced.
Administrative modules and cross-tenant data are inaccessible. Deletion uses safe archive if supported.
Search criteria are limited to one equals / starts_with / contains expression; list queries are bounded.

## Connection-scoped invokeurl
Bracketed invokeurl accepts url, type (GET/POST/PUT/PATCH/DELETE), connection, body, parameters and headers.
Execution is ASYNCHRONOUS: assigning its result receives a queue receipt, not an HTTP response.
Scripts cannot choose arbitrary endpoints. Worker accepts only the exact HTTPS URL configured for the named connection.
Worker rejects redirects, script-supplied Authorization/Cookie headers, oversized payloads and oversized responses.

## Server configuration
Set DELUGE_HTTP_CONNECTIONS_JSON on the worker, e.g.
{"partner":{"enabled":true,"url":"https://api.partner.example.com/hooks","methods":["POST"],"auth_type":"OAuth2","token_url":"https://auth.partner.example.com/oauth/token","refresh_token_env":"PARTNER_REFRESH_TOKEN","client_id_env":"PARTNER_CLIENT_ID","client_secret_env":"PARTNER_CLIENT_SECRET"}}
Set secret values in environment variables through the deployment secret manager, never in script text.
OAuth2 supports a pre-authorized access_token_env or an externally obtained refresh token with refresh grant.
Initial interactive consent is not implemented; users must authorize externally before configuring refresh credentials.

## Not equivalent to complete Zoho runtime
No synchronous HTTP response assignment, multipart/files, broad connection lifecycle UI, complete OAuth consent flow,
all standard language built-ins, Zoho API result envelopes or all Zoho CRM task options and data types.
Do not mark complete Zoho Deluge parity without an official conformance suite and required provider authorization.
