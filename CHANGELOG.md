# Changelog

## [0.1.0.0] - 2026-10-01

### Added

- Added functional CRM modules for activities, inventory and sales, marketing, service, documents, forecasts, reports and dashboards.
- Added the complete Setup directory for general administration, security, customization, automation, templates, data administration and developer settings.
- Added extensible platform records with ownership, audit metadata, relationships, filtering, sorting, archiving, recycle-bin restoration and duplicate scanning.
- Added configurable workflow and assignment foundations, role/profile/permission records, pipelines, custom views, templates, API settings, webhooks and integrations.
- Added CSV import/export foundations, audit history and a second database migration for platform records, audit events and import jobs.
- Added contract coverage for expanded CRUD, activity subtypes, lead conversion, related records, automation execution, profile email persistence and recycle/restore.

### Changed

- Expanded the existing Yash CRM navigation while retaining its branding, responsive theme and latest workspace styling.
- Strengthened lead conversion so retries reuse the existing account, contact and conversion deal instead of creating duplicates.
- Refactored reusable module definitions into a central platform catalog and added dialect-safe database engine configuration.
- Updated the service worker and route manifest for the expanded application.

### Fixed

- Preserved Railway and Render readiness behavior, trusted-host boundaries and deployment-only files while replacing the application source.
- Allowed decimal values in numeric CRM fields and lead-conversion deal amounts.
