from mcp.server.fastmcp import FastMCP

from source360.api import bid_matrix, category_spend, evidence, scorecard

mcp = FastMCP("Source360 read-only evidence")


@mcp.tool()
def get_category_spend(category_id: int) -> dict:
    return category_spend(category_id)


@mcp.tool()
def get_supplier_scorecard(supplier_id: int) -> dict:
    return scorecard(supplier_id)


@mcp.tool()
def get_rfq_bid_matrix(rfq_id: str) -> list:
    return bid_matrix(rfq_id)


@mcp.tool()
def get_contract_evidence(contract_id: str) -> dict:
    return evidence(contract_id)


if __name__ == "__main__":
    mcp.run(transport="stdio")
