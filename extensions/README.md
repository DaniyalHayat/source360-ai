# Optional adapters

- `mcp/server.py`: install `pip install '.[mcp]'`, then run `python -m extensions.mcp.server` from the root after the pipeline. Uses the MCP SDK FastMCP stdio transport; explicit read-only tools only. No arbitrary query or sourcing action is exposed.
- `databricks/spend_cleaning.py`: call clean_spend(po_dataframe, supplier_dataframe) in a PySpark environment. It reproduces alias matching, currency normalization and rejection of invalid financial rows. No Databricks workspace, distributed job or throughput result is claimed.
- Airflow: `airflow/dags/procurement_daily.py` targets Airflow 3's SDK. Install the project and dbt in the Airflow environment, mount the source extracts, configure DATABASE_URL/DBT_HOST and discover the DAG. Generation is an explicit bootstrap step, not a task that silently replaces sources every day. Scheduler execution is not part of core Compose.

Semantic RAG and trained AI extraction are deferred. The deterministic evidence workflow is implemented and tested.
