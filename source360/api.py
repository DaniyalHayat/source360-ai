import csv
import io
import json
from functools import lru_cache
from pathlib import Path

import numpy as np
from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import FileResponse, Response
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import text

from source360.database import engine, read, records
from source360.documents import extract
from source360.forecast import forecast
from source360.optimization import optimize

app = FastAPI(
    title="Source360 AI",
    version="1.0.0",
    description="Synthetic procurement decision support. No supplier awards are executed.",
)
WEB = Path(__file__).resolve().parents[1] / "web"


def table(name):
    return cached_table(name, latest_run()["input_snapshot_id"])


@lru_cache(maxsize=32)
def cached_table(name, snapshot):
    return read(name)


def find(frame, key, value):
    rows = frame[frame[key] == value]
    if rows.empty:
        raise HTTPException(404, f"Unknown {key}")
    return records(rows)[0]


def latest_run():
    with engine.connect() as conn:
        rows = conn.execute(text("SELECT payload FROM pipeline_runs")).all()
    if not rows:
        raise HTTPException(503, "Run the pipeline first")
    return max((json.loads(row[0]) for row in rows), key=lambda run: run["timestamp"])


@app.get("/health")
def health():
    return dict(
        status="ok", synthetic=True, database=engine.dialect.name, snapshot=latest_run()["snapshot_date"]
    )


@app.get("/api/v1/categories")
def categories():
    return records(table("dim_category"))


@app.get("/api/v1/overview")
def overview(category_id: int | None = None):
    spend = table("fct_spend")
    if category_id:
        find(table("dim_category"), "category_id", category_id)
        spend = spend[spend.category_id == category_id]
    total = float(spend.extended_spend_usd.sum())
    category = (
        spend.groupby("category_id").extended_spend_usd.sum().reset_index().merge(table("dim_category"))
    )
    supplier = table("supplier_metrics")
    if category_id:
        supplier = supplier[supplier.category_id == category_id]
    annual = spend[spend.order_date >= "2025-11-01"]
    by_month = spend.groupby("month").extended_spend_usd.sum().reset_index()
    return dict(
        total_spend=total,
        period="2023-11 to 2026-10",
        annual_spend=float(annual.extended_spend_usd.sum()),
        supplier_count=int(spend.supplier_id.nunique()),
        po_lines=len(spend),
        off_contract_spend=float(spend.loc[spend.off_contract_flag == 1, "extended_spend_usd"].sum()),
        anomaly_spend=float(spend.loc[spend.price_anomaly == 1, "extended_spend_usd"].sum()),
        on_time_rate=float(spend.on_time.sum() / max(spend.delivery_observed.sum(), 1)),
        category_spend=records(category.sort_values("extended_spend_usd", ascending=False)),
        supplier_risk=records(supplier),
        monthly_spend=records(by_month),
        pipeline=latest_run(),
        sourcing_opportunity="Off-contract and anomaly exposure are review populations, not additive savings.",
    )


@app.get("/api/v1/categories/{category_id}/spend")
def category_spend(category_id: int):
    return overview(category_id)


def category_forecast_data(category_id):
    return cached_forecast(category_id, latest_run()["input_snapshot_id"])


@lru_cache(maxsize=20)
def cached_forecast(category_id, snapshot):
    find(table("dim_category"), "category_id", category_id)
    return forecast(table("monthly_spend")[lambda f: f.category_id == category_id])


@app.get("/api/v1/categories/{category_id}/forecast")
def category_forecast(category_id: int):
    return category_forecast_data(category_id)


@app.get("/api/v1/suppliers")
def suppliers():
    return records(table("supplier_metrics").sort_values("spend_usd", ascending=False))


@app.get("/api/v1/portfolio/scenarios")
def portfolio_scenarios():
    from source360.portfolio import evaluate_portfolio
    events = rfqs()
    bid_sets = {event["rfq_id"]: bid_matrix(event["rfq_id"]) for event in events}
    return evaluate_portfolio(events, bid_sets, snapshot=latest_run()["input_snapshot_id"], draws=1000)


@app.get("/api/v1/suppliers/{supplier_id}/scorecard")
def scorecard(supplier_id: int):
    return find(table("supplier_metrics"), "supplier_id", supplier_id)


@app.get("/api/v1/rfqs")
def rfqs():
    return records(table("rfq_events").merge(table("dim_category"), on="category_id"))


@app.get("/api/v1/rfqs/{rfq_id}/bids")
def bid_matrix(rfq_id: str):
    find(table("rfq_events"), "rfq_id", rfq_id)
    bids = table("rfq_bids")[lambda f: f.rfq_id == rfq_id]
    return records(
        bids.merge(
            table("supplier_metrics")[["supplier_id", "canonical_name", "risk_score"]], on="supplier_id"
        )
    )


class ScenarioInput(BaseModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)
    demand: float | None = Field(default=None, ge=1, le=10_000_000)
    risk_penalty: float = Field(default=100, ge=0, le=10000)
    max_share: float = Field(default=0.60, ge=0.1, le=1)
    min_suppliers: int = Field(default=2, ge=1, le=4)
    max_suppliers: int = Field(default=3, ge=1, le=4)
    qualified_share: float = Field(default=0.3, ge=0, le=1)
    capacity_factor: float = Field(default=1, ge=0.1, le=2)
    logistics_factor: float = Field(default=1, ge=0, le=5)
    seed: int = Field(default=360, ge=0, le=2**32 - 1)
    draws: int = Field(default=5000, ge=1000, le=10000)


@app.post("/api/v1/rfqs/{rfq_id}/scenarios")
def scenario(rfq_id: str, params: ScenarioInput):
    if params.min_suppliers > params.max_suppliers:
        raise HTTPException(422, "Minimum suppliers exceeds maximum")
    rfq = find(table("rfq_events"), "rfq_id", rfq_id)
    result = optimize(
        rfq, bid_matrix(rfq_id), snapshot=latest_run()["input_snapshot_id"], **params.model_dump()
    )
    with engine.begin() as conn:
        conn.execute(text("DELETE FROM scenario_runs WHERE scenario_id=:id"), {"id": result["scenario_id"]})
        conn.execute(
            text("INSERT INTO scenario_runs VALUES (:id,:rfq,:payload)"),
            dict(id=result["scenario_id"], rfq=rfq_id, payload=json.dumps(result)),
        )
    return result


@app.get("/api/v1/rfqs/{rfq_id}/scenarios/{scenario_id}")
def saved_scenario(rfq_id: str, scenario_id: str):
    with engine.connect() as conn:
        row = conn.execute(
            text("SELECT payload FROM scenario_runs WHERE scenario_id=:id AND rfq_id=:rfq"),
            dict(id=scenario_id, rfq=rfq_id),
        ).first()
    if not row:
        raise HTTPException(404, "Scenario not found")
    return json.loads(row[0])


@app.get("/api/v1/rfqs/{rfq_id}/sensitivity")
def sensitivity(rfq_id: str):
    rfq = find(table("rfq_events"), "rfq_id", rfq_id)
    bids = bid_matrix(rfq_id)
    out = []
    for factor in [0.8, 0.9, 1, 1.1, 1.2]:
        result = optimize(
            rfq, bids, demand=rfq["demand"] * factor, draws=1000, snapshot=latest_run()["input_snapshot_id"]
        )
        out.append(
            dict(
                demand_factor=factor,
                status=result["status"],
                landed_cost=result.get("landed_cost"),
                savings_pct=result.get("savings_pct"),
            )
        )
    return out


@app.get("/api/v1/data-quality/status")
def quality():
    return dict(
        checks=records(table("dq_results")),
        run=latest_run(),
        quarantine_sample=records(table("quarantine").head(12)),
        live_age_days=max(0, int((np.datetime64("today") - np.datetime64("2026-10-30")).astype(int))),
        freshness_basis="Historical synthetic snapshot as of 2026-10-30; not a live feed",
    )


@app.get("/api/v1/pipeline/runs/{run_id}")
def pipeline_run(run_id: str):
    with engine.connect() as conn:
        row = conn.execute(text("SELECT payload FROM pipeline_runs WHERE run_id=:id"), {"id": run_id}).first()
    if not row:
        raise HTTPException(404, "Run not found")
    return json.loads(row[0])


class DocumentInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    document_id: str = Field(max_length=100, min_length=1)
    text: str = Field(max_length=100_000, min_length=1)


@app.post("/api/v1/documents/extract")
def document_extract(document: DocumentInput):
    return extract(document.text, document.document_id)


@app.get("/api/v1/documents")
def documents(q: str = Query(default="", max_length=100)):
    frame = table("contracts")
    if q:
        frame = frame[frame.text.str.contains(q, case=False, regex=False)]
    return records(frame.head(120))


@app.get("/api/v1/documents/{document_id}/evidence")
def evidence(document_id: str):
    doc = find(table("contracts"), "document_id", document_id)
    return dict(**doc, extraction=extract(doc["text"], document_id))


@app.get("/api/v1/export/{dataset}")
def export(dataset: str):
    if dataset not in {"supplier_metrics", "monthly_spend", "rfq_bids", "dq_results"}:
        raise HTTPException(404, "Export unavailable")
    data = table(dataset)
    out = io.StringIO()
    writer = csv.writer(out)
    writer.writerow(data.columns)
    for row in data.itertuples(index=False, name=None):
        writer.writerow(
            ["'" + v if isinstance(v, str) and v.startswith(("=", "+", "-", "@")) else v for v in row]
        )
    return Response(
        out.getvalue(),
        media_type="text/csv",
        headers={"Content-Disposition": f'attachment; filename="{dataset}.csv"'},
    )


@app.get("/")
def home():
    return FileResponse(WEB / "index.html")


class AssistantInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    question: str = Field(min_length=3, max_length=500)
    supplier_id: int = Field(default=1, ge=1, le=60)


def assistant_engine():
    return cached_assistant(latest_run()["input_snapshot_id"])


@lru_cache(maxsize=1)
def cached_assistant(snapshot):
    from extensions.rag.assistant import EvidenceAssistant

    return EvidenceAssistant()


@app.post("/api/v1/assistant/answer")
def assistant_answer(request: AssistantInput):
    return assistant_engine().answer(request.question, request.supplier_id)


app.mount("/static", StaticFiles(directory=WEB), name="static")
