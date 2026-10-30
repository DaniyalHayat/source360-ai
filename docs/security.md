# Security and governance

Only synthetic records are included. No credentials or real supplier documents are needed. Local services bind to 127.0.0.1. The public artifact consists of intentionally public synthetic JSON/JS/HTML/CSS, with no private database or credentials. The demo does not implement enterprise authentication, row-level tenancy, approval-role enforcement, or operational procurement actions. Do not expose the FastAPI/Compose edition publicly without those controls.

API queries use bound values. Dynamic table names are allowlisted. Scenario inputs reject extra fields, nonfinite values and unsupported ranges. Document extraction accepts a bounded plain-text JSON schema, not arbitrary file uploads. HTML content is escaped before rendering. Browser search is literal, not regex. CSV export guards leading formula characters. Raw source hashes are verified before ingestion. Solver runtime and simulation draw counts are bounded.

Documents are untrusted content. Their instructions are never executed. The MCP adapter exposes explicit read-only lookups with no SQL tool, external messaging or award operation. All recommendations state that human review is required. Exported JSON contains commercial assumptions and immutable snapshot IDs, not actual approvals.

Optional AWS design: private S3 bucket, Block Public Access, encryption, scoped prefix access, lifecycle cleanup, account budget and usage monitoring. No free-tier entitlement or zero cloud cost is promised. Cloud provisioning and cost verification were not performed.
