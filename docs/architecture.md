# Architecture and decisions

Local edition: seeded extracts -> validated Python ingestion -> SQLite -> analytics/FastAPI -> browser. PostgreSQL edition: same raw controls -> PostgreSQL public landing tables -> independent dbt SQL transformations into analytics schema -> FastAPI configured with SOURCE360_DBT_MARTS=1. SQL/Python parity tests prevent drift in published spend, off-contract status, delivery flags and anomalies. Feature metrics remain derived by Python from the same clean records.

The generator manifest hashes the exact source files. A changed raw source without a new manifest fails publication. The pipeline stages data and publishes in one database transaction. It replaces the current analytical snapshot; concurrent ingestion and serving is not an enterprise availability guarantee. API tables are process-cached: restart the API after a CLI pipeline refresh. Scenario receipts preserve their original complete inputs even after the current snapshot changes.

The public edition exports aggregate/scorecard/contract/bid data and forecasts from the API. Its specialized exact browser optimizer evaluates new user inputs locally. It has no central API or upload service and never transmits scenario inputs to suppliers. Session receipts are stored per browser session and downloaded on request. Python and browser input hashes use their own documented serialization and are not cross-runtime identity claims.

## Technology decisions

| Choice | Reason / boundary |
|---|---|
| PostgreSQL | Relational warehouse, governed SQL and local containers; SQLite is explicit portable fallback |
| S3 | Optional immutable raw archive; local raw directory is the executed landing zone; no AWS resources provisioned |
| PuLP/CBC | Inspectable single-item supplier allocation; no commercial solver licensing requirement |
| dbt | Independently recomputes canonical financial marts and tests against the ingestion reference |
| Airflow | Optional scheduled batch orchestration; workflow DAG is supplied separately from the core Compose stack |
| Figma/browser app | Recruiter-requested interactive presentation surface; full backend remains downloadable |
| Power BI | Secondary authoring kit, no fabricated PBIX binary |
| MongoDB | Deferred: relational contracts and metadata do not justify another operational store |
| Kafka | Deferred: nightly procurement snapshots do not require an event stream |
| Spark/Databricks | Optional transformation adapter, not a runtime dependency at this scale |
| Snowflake | Deferred warehouse alternative, not required for the local/public demonstration |
| Hadoop/HBase | Deferred: no demonstrated distributed storage requirement |

The SQL Server/MySQL source systems are file-shaped simulations, not running installations or live enterprise connectors. Current source CSVs are intentionally heterogeneous but finite and synthetic.
