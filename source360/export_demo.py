import json
import shutil

from fastapi.testclient import TestClient

from source360.api import app
from source360.settings import ROOT


def export_demo():
    client = TestClient(app)
    out = ROOT / "dist"
    assets = out / "static"
    assets.mkdir(parents=True, exist_ok=True)
    data = {
        "categories": client.get("/api/v1/categories").json(),
        "rfqs": client.get("/api/v1/rfqs").json(),
        "suppliers": client.get("/api/v1/suppliers").json(),
        "quality": client.get("/api/v1/data-quality/status").json(),
        "documents": client.get("/api/v1/documents").json(),
        "forecasts": {},
        "bids": {},
        "evidence": {},
        "overviews": {},
        "warehouse": client.get('/api/v1/warehouse/status').json(),
    }
    for c in data["categories"]:
        cid = c["category_id"]
        data["forecasts"][cid] = client.get(f"/api/v1/categories/{cid}/forecast").json()
        data["overviews"][cid] = client.get(f"/api/v1/overview?category_id={cid}").json()
    data["overviews"]["all"] = client.get("/api/v1/overview").json()
    for rfq in data["rfqs"]:
        data["bids"][rfq["rfq_id"]] = client.get(f"/api/v1/rfqs/{rfq['rfq_id']}/bids").json()
    for doc in data["documents"]:
        data["evidence"][doc["document_id"]] = client.get(
            f"/api/v1/documents/{doc['document_id']}/evidence"
        ).json()
    portfolio = dict(rfqs=data['rfqs'], bids=data['bids'], capacities=client.get('/api/v1/suppliers/capacities').json(),
                     snapshot=data['quality']['run']['input_snapshot_id'], warehouse=data['warehouse'])
    (ROOT / 'web/portfolio-input.json').write_text(json.dumps(portfolio, separators=(',', ':')), encoding='utf-8')
    (assets / "demo-data.json").write_text(json.dumps(data, separators=(",", ":")), encoding="utf-8")
    for name in [
        "app.js",
        "style.css",
        "browser-engine.js",
        "demo-adapter.js",
        "recruiter.js",
        "recruiter.css",
        "ai-evidence.js",
        "ai-evidence-data.json",
        "portfolio.html", "portfolio.css", "portfolio.mjs", "portfolio-input.json", "joint-engine.mjs", "joint-worker.mjs",
    ]:
        shutil.copy2(ROOT / "web" / name, assets / name)
    portfolio_page = assets / 'portfolio.html'
    portfolio_page.write_text(portfolio_page.read_text(encoding='utf-8').replace('<body>','<body data-delivery="snapshot">',1), encoding='utf-8')
    shutil.copytree(ROOT / 'web/vendor', assets / 'vendor', dirs_exist_ok=True)
    html = (ROOT / "web/index.html").read_text(encoding="utf-8")
    html = html.replace(
        '<script src="/static/app.js" defer></script>',
        '<script src="./static/browser-engine.js" defer></script>\n'
        '<script src="./static/demo-adapter.js" defer></script>\n'
        '<script src="./static/app.js" defer></script>',
    )
    html = html.replace('href="/static/style.css"', 'href="./static/style.css"')
    html = html.replace('href="/static/recruiter.css"', 'href="./static/recruiter.css"')
    html = html.replace('src="/static/recruiter.js"', 'src="./static/recruiter.js"')
    html = html.replace('src="/static/ai-evidence.js"', 'src="./static/ai-evidence.js"')
    html = html.replace('href="/static/portfolio.html"', 'href="./static/portfolio.html"')
    html = html.replace("Local decision engine", "Browser decision engine")
    html = html.replace(
        '<a href="/docs" target="_blank" rel="noopener">API reference ↗</a>',
        '<button class="text-link" id="about-project">About this project ↗</button>',
    )
    (out / "index.html").write_text(html, encoding="utf-8")
    return dict(directory=str(out), bytes=(assets / "demo-data.json").stat().st_size)


if __name__ == "__main__":
    print(json.dumps(export_demo()))
