import json
import shutil
import subprocess

import pytest

from source360.optimization import optimize


def test_browser_optimizer_matches_cbc(client):
    node = shutil.which("node")
    if not node:
        pytest.skip("Node is required for browser-engine parity verification")
    rfqs = client.get("/api/v1/rfqs").json()
    cases = []
    for rfq in rfqs[:10]:
        bids = client.get(f"/api/v1/rfqs/{rfq['rfq_id']}/bids").json()
        for params in [
            {"risk_penalty": 0, "max_share": 0.7, "qualified_share": 0.2, "min_suppliers": 1},
            {"risk_penalty": 100},
            {"risk_penalty": 400, "max_share": 0.45, "qualified_share": 0.6, "min_suppliers": 3},
            {"demand": rfq["demand"] * 1.2},
            {"demand": rfq["demand"] * 8},
        ]:
            cases.append(dict(rfq=rfq, bids=bids, params={**params, "draws": 1000}))
    js = "const e=require('./web/browser-engine.js');let s='';process.stdin.on('data',v=>s+=v);process.stdin.on('end',()=>console.log(JSON.stringify(JSON.parse(s).map(c=>e.optimize(c.rfq,c.bids,c.params)))));"
    proc = subprocess.run(
        [node, "-e", js], input=json.dumps(cases), capture_output=True, text=True, check=True
    )
    results = json.loads(proc.stdout)
    for case, browser in zip(cases, results):
        python = optimize(case["rfq"], case["bids"], **case["params"])
        assert browser["status"] == python["status"]
        if python["status"] == "Optimal":
            assert browser["objective_value"] == pytest.approx(python["objective_value"], abs=0.02)
            assert browser["landed_cost"] == pytest.approx(python["landed_cost"], abs=0.02)
            assert all(browser["constraint_checks"].values())
