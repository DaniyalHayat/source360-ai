from datetime import datetime

from airflow.sdk import DAG, task

with DAG(
    "source360_daily_procurement",
    schedule="0 6 * * *",
    start_date=datetime(2026, 1, 1),
    catchup=False,
    tags=["synthetic", "procurement"],
) as dag:

    @task
    def reconcile_sources():
        from source360.pipeline import run_pipeline

        return run_pipeline()

    @task
    def build_governed_marts(receipt):
        import subprocess

        from source360.settings import ROOT

        subprocess.run(
            ["dbt", "build", "--project-dir", str(ROOT / "dbt"), "--profiles-dir", str(ROOT / "dbt")],
            check=True,
        )
        return receipt

    @task
    def publish_receipt(receipt):
        if receipt["status"] != "passed":
            raise ValueError("Publication requires a passing reconciliation receipt")
        return {"snapshot": receipt["input_snapshot_id"], "status": "available_for_human_review"}

    publish_receipt(build_governed_marts(reconcile_sources()))
