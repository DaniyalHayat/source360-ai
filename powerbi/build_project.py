import json
from pathlib import Path

import pandas as pd

from source360.api import ScenarioInput, category_forecast_data, overview, quality, scenario, portfolio_scenarios, warehouse_status
from source360.database import read

ROOT = Path(__file__).resolve().parent


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2), encoding="utf-8")


def m_literal(v):
    if v is None or pd.isna(v):
        return "null"
    if isinstance(v, (int, float)):
        return str(v)
    return '"' + str(v).replace('"', '""') + '"'


def build():
    project = ROOT / "Source360"
    dataset = project / "Source360.SemanticModel"
    report = project / "Source360.Report"
    category = pd.DataFrame(overview()["category_spend"])[["name", "extended_spend_usd"]].rename(
        columns={"name": "Category", "extended_spend_usd": "Spend"}
    )
    monthly = (
        read("monthly_spend")
        .groupby("month")
        .spend_usd.sum()
        .reset_index()
        .rename(columns={"month": "Month", "spend_usd": "Spend"})
    )
    supplier = read("supplier_metrics")[["canonical_name", "spend_usd", "risk_score", "on_time_rate"]].rename(
        columns={
            "canonical_name": "Supplier",
            "spend_usd": "Spend",
            "risk_score": "Risk",
            "on_time_rate": "OnTime",
        }
    )
    kpi = overview()
    executive = pd.DataFrame(
        [
            {
                "TotalSpend": kpi["total_spend"],
                "AnnualSpend": kpi["annual_spend"],
                "OffContract": kpi["off_contract_spend"],
                "OnTime": kpi["on_time_rate"],
            }
        ]
    )
    award = scenario("RFQ-001", ScenarioInput())
    sourcing = pd.DataFrame([{
        "Supplier": a["name"], "Quantity": a["quantity"], "Share": a["share"],
        "CashCost": a["cost"], "Risk": a["risk_score"],
    } for a in award["allocations"]])
    decision = pd.DataFrame([{
        "Baseline": award["baseline_cost"], "CashCost": award["landed_cost"],
        "ModeledSavings": award["savings"], "SavingsRate": award["savings_pct"],
        "CostP10": award["uncertainty"]["cost_p10"],
        "CostP90": award["uncertainty"]["cost_p90"],
    }])
    forecast = pd.DataFrame(category_forecast_data(1)["forecast"]).rename(
        columns={"month": "Month", "spend": "ExpectedSpend", "low": "Low", "high": "High"}
    )
    controls = pd.DataFrame(quality()["checks"])[["check_name", "passed", "observed", "threshold"]]
    joint = portfolio_scenarios()
    portfolio = pd.DataFrame([dict(Event=r['rfq_id'], Baseline=r['baseline_cost'], CashCost=r['landed_cost'],
        ModeledSavings=r['baseline_cost']-r['landed_cost']) for r in joint['results']])
    capacity = pd.DataFrame(joint['supplier_capacity']).rename(columns={
        'supplier_id':'SupplierID','capacity_period':'Period','unit':'Unit','capacity':'Budget','used':'Used','slack':'Remaining'})
    capacity = capacity[['SupplierID','Period','Unit','Budget','Used','Remaining']]
    priorities = pd.DataFrame(warehouse_status()['categories']).rename(columns={
        'name':'Category','spend_usd':'Spend','off_contract_usd':'OffContractReview','po_lines':'PurchaseLines','supplier_count':'Suppliers'})
    frames = {"Categories": category, "Monthly": monthly, "Suppliers": supplier,
              "Executive": executive, "Award": sourcing, "Decision": decision,
              "Forecast": forecast, "Controls": controls, "Portfolio":portfolio, "Capacity":capacity, "Priorities":priorities}
    tables = []
    for name, frame in frames.items():
        columns = [
            {
                "name": c,
                "dataType": "double" if pd.api.types.is_numeric_dtype(frame[c]) else "string",
                "sourceColumn": c,
            }
            for c in frame
        ]
        for column in columns:
            if column["dataType"] == "double":
                column["formatString"] = "0.0%" if column["name"] in {"OnTime", "Share", "SavingsRate"} else "#,0.00"
        schema = ",".join(
            f"{c} = " + ("number" if pd.api.types.is_numeric_dtype(frame[c]) else "text") for c in frame
        )
        rows = ",".join(
            "{" + ",".join(m_literal(v) for v in row) + "}"
            for row in frame.itertuples(index=False, name=None)
        )
        tables.append(
            {
                "name": name,
                "columns": columns,
                "partitions": [
                    {
                        "name": name,
                        "mode": "import",
                        "source": {
                            "type": "m",
                            "expression": [
                                f"let Source = #table(type table [{schema}], {{{rows}}}) in Source"
                            ],
                        },
                    }
                ],
            }
        )
    write(dataset / "definition.pbism", {"version": "4.0", "settings": {}})
    write(
        dataset / "model.bim",
        {
            "name": "Source360",
            "compatibilityLevel": 1600,
            "model": {"culture": "en-US", "defaultPowerBIDataSourceVersion": "powerBI_V3", "tables": tables},
        },
    )
    write(
        project / "Source360.pbip",
        {
            "version": "1.0",
            "artifacts": [{"report": {"path": "Source360.Report"}}],
            "settings": {"enableAutoRecovery": True},
        },
    )
    write(
        report / "definition.pbir",
        {"version": "4.0", "datasetReference": {"byPath": {"path": "../Source360.SemanticModel"}}},
    )
    write(
        report / "definition/version.json",
        {
            "$schema": "https://developer.microsoft.com/json-schemas/fabric/item/report/definition/versionMetadata/1.0.0/schema.json",
            "version": "2.0.0",
        },
    )
    write(
        report / "definition/report.json",
        {
            "$schema": "https://developer.microsoft.com/json-schemas/fabric/item/report/definition/report/3.1.0/schema.json",
            "themeCollection": {},
            "settings": {"useStylableVisualContainerHeader": True},
        },
    )
    pages = [
        ("executive", "Executive | synthetic sourcing"),
        ("suppliers", "Supplier performance"),
        ("sourcing", "Modeled award | IT Hardware"),
        ("forecast", "IT Hardware outlook | illustrative bands"),
        ("controls", "Financial controls"),
        ("portfolio", "25-event portfolio | synthetic shared capacity"),
        ("capacity", "Shared annual supplier capacity | planning proxy"),
        ("priorities", "Off-contract review | not modeled savings"),
    ]
    write(
        report / "definition/pages/pages.json",
        {
            "$schema": "https://developer.microsoft.com/json-schemas/fabric/item/report/definition/pagesMetadata/1.0.0/schema.json",
            "pageOrder": [p[0] for p in pages],
            "activePageName": "executive",
        },
    )
    for page, title in pages:
        write(
            report / f"definition/pages/{page}/page.json",
            {
                "$schema": "https://developer.microsoft.com/json-schemas/fabric/item/report/definition/page/2.0.0/schema.json",
                "name": page,
                "displayName": title,
                "displayOption": "FitToPage",
                "height": 720,
                "width": 1280,
            },
        )

    def visual(page, name, kind, entity, fields, x, y, width, height):
        query = {}
        for role, col, aggregate in fields:
            field = {"Column": {"Expression": {"SourceRef": {"Entity": entity}}, "Property": col}}
            ref = f"{entity}.{col}"
            if aggregate:
                field = {"Aggregation": {"Expression": field, "Function": 0}}
                ref = f"Sum({ref})"
            query.setdefault(role, {"projections": []})["projections"].append(
                {"field": field, "queryRef": ref, "nativeQueryRef": col}
            )
        write(
            report / f"definition/pages/{page}/visuals/{name}/visual.json",
            {
                "$schema": "https://developer.microsoft.com/json-schemas/fabric/item/report/definition/visualContainer/2.7.0/schema.json",
                "name": name,
                "position": {"x": x, "y": y, "z": 0, "height": height, "width": width, "tabOrder": 0},
                "visual": {
                    "visualType": kind,
                    "query": {"queryState": query},
                    "drillFilterOtherVisuals": True,
                },
            },
        )

    for i, col in enumerate(executive):
        visual(
            "executive", f"kpi{i}", "card", "Executive", [("Values", col, True)], 20 + i * 310, 20, 290, 150
        )
    visual(
        "executive",
        "categories",
        "clusteredBarChart",
        "Categories",
        [("Category", "Category", False), ("Y", "Spend", True)],
        20,
        190,
        600,
        490,
    )
    visual(
        "executive",
        "monthly",
        "lineChart",
        "Monthly",
        [("Category", "Month", False), ("Y", "Spend", True)],
        640,
        190,
        620,
        490,
    )
    visual(
        "suppliers",
        "directory",
        "tableEx",
        "Suppliers",
        [("Values", c, False) for c in supplier],
        20,
        20,
        1240,
        660,
    )
    visual(
        "controls",
        "totals",
        "tableEx",
        "Controls",
        [("Values", c, False) for c in controls],
        20,
        20,
        1240,
        660,
    )
    for i, col in enumerate(decision):
        visual("sourcing", f"decision{i}", "card", "Decision", [("Values", col, True)],
               20 + (i % 3) * 415, 20 + (i // 3) * 145, 395, 130)
    visual("sourcing", "allocation", "tableEx", "Award",
           [("Values", c, False) for c in sourcing], 20, 330, 1240, 350)
    visual("forecast", "outlook", "lineChart", "Forecast",
           [("Category", "Month", False), ("Y", "ExpectedSpend", True),
            ("Y", "Low", True), ("Y", "High", True)], 20, 20, 1240, 660)
    visual('portfolio','joint-awards','tableEx','Portfolio',[("Values",c,False) for c in portfolio],20,20,1240,660)
    visual('capacity','shared-budgets','tableEx','Capacity',[("Values",c,False) for c in capacity],20,20,1240,660)
    visual('priorities','review-exposure','clusteredBarChart','Priorities',
        [('Category','Category',False),('Y','OffContractReview',True)],20,20,1240,660)
    print(project / "Source360.pbip")


if __name__ == "__main__":
    build()
