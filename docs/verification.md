# Verification record

Executed on October 30, 2026. This is a technical portfolio demonstration using synthetic data.

| Area | Evidence / status |
|---|---|
| Seeded pipeline | 100,000 raw PO lines; 99,816 published; 184 quarantined; 425 duplicate invoice IDs removed |
| Financial bridge | Unexplained signed-USD PO difference below $0.01 |
| Python/API | Automated pytest suite; machine-readable latest result in test-results.xml |
| Browser optimizer | 50 cases compared with PuLP/CBC across ten categories, three presets, demand stress and infeasibility |
| Forecast | Every category export checked; scaled least-squares ETS fitting, rolling baseline validation |
| PostgreSQL/dbt | Docker image build, ingestion and dbt build executed; four models and ten data tests passed |
| Public UX | Browser tour, sourcing scenario and strategy comparison checked; publication details tracked in delivery.json when available |
| Figma | Standalone Figma Make app imported and running; supplier award executed in its preview. Publishing status is in the delivery receipt. Editable native Design shapes are not claimed |
| Power BI | Five-page native PBIP opened/refreshed/rendered, then saved as a 61,854-byte PBIX with DataModel and report definitions; executive and sourcing screenshots included |
| Airflow | Airflow 3.1 container executed all three DAG tasks successfully against PostgreSQL; `airflow-verification.json`; no permanent scheduler claimed |
| MCP | Actual SDK stdio client initialized, listed and called all four tools; `mcp-verification.json` |
| PySpark | Spark 4.2.1 / Java 17 ran on 100,000 raw rows; 99,816-row output and spend matched Python; `spark-verification.json`; no hosted Databricks claim |
| AI assistant | MiniLM embeddings and FLAN-T5 generation executed locally; 5/5 retrieval and answer checks; exact citations; `rag-evaluation.json`; benchmark is small and synthetic |
| AWS | Private CloudFormation/S3 deployment in us-east-2, 851-byte checksum round trip, encryption/public-block/versioning checks and stack cleanup verified; `aws-verification.json` |

## Extension reproduction

Install `requirements-extensions.txt` in addition to the core requirements. Run `python extensions/verify_mcp.py`, `python extensions/verify_spark.py` with Java 17 available, and `python -m extensions.rag.evaluate`. Generate the native Power BI project with `python -m powerbi.build_project`, then open `powerbi/Source360/Source360.pbip` and refresh.

Build Airflow with `docker build -f Dockerfile.airflow -t source360-airflow .`. With Compose PostgreSQL running, execute `docker run --rm --network source360-ai_default -e DATABASE_URL=postgresql+psycopg://source360:local_demo_only@db:5432/source360 -e DBT_HOST=db --entrypoint bash source360-airflow -c "airflow db migrate && airflow dags test source360_daily_procurement 2026-10-30"`. Airflow's own dependencies and the application's dependencies use separate environments.

AWS verification is opt-in and creates then deletes its own disposable stack: set `AWS_PROFILE=source360` and run `python cloud/verify_aws.py --region us-east-2`. The $5 budget is an authorization limit, not an AWS hard billing cap; no claim of a finalized zero-dollar bill is made. The public demo runs independently of AWS and the laptop.

No pre-commit configuration was present. No realized savings, real client engagement, production enterprise controls or operational AI agent is claimed.
