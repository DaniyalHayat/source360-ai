import json
import os

import pandas as pd
from sqlalchemy import create_engine, text

from source360.settings import DATABASE_URL


def engine_for(url=DATABASE_URL):
    return create_engine(url, connect_args={"check_same_thread": False} if url.startswith("sqlite") else {})


engine = engine_for()


def read(table, db=engine):
    allowed = {
        "dim_supplier",
        "dim_category",
        "fct_spend",
        "ap_invoices",
        "rfq_events",
        "rfq_bids",
        "contracts",
        "communications",
        "market_indices",
        "supplier_metrics",
        "monthly_spend",
        "quarantine",
        "dq_results",
        "pipeline_runs",
        "scenario_runs",
        "source_po",
    }
    if table not in allowed:
        raise ValueError("Unknown table")
    schema = (
        "analytics."
        if os.getenv("SOURCE360_DBT_MARTS") == "1" and table in {"fct_spend", "monthly_spend", "dim_supplier"}
        else ""
    )
    with db.connect() as conn:
        frame = pd.read_sql(text(f'SELECT * FROM {schema}"{table}"'), conn)
    if "order_date" in frame and not frame.empty:
        frame["order_date"] = frame.order_date.astype(str)
    return frame


def records(frame):
    return json.loads(frame.to_json(orient="records", date_format="iso"))
