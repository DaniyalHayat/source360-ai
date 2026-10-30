import asyncio
import json
import sys

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client


async def main():
    async with stdio_client(
        StdioServerParameters(command=sys.executable, args=["-m", "extensions.mcp.server"])
    ) as (r, w):
        async with ClientSession(r, w) as session:
            await session.initialize()
            tools = await session.list_tools()
            assert {t.name for t in tools.tools} == {
                "get_category_spend",
                "get_supplier_scorecard",
                "get_rfq_bid_matrix",
                "get_contract_evidence",
            }
            receipts = []
            for name, args in [
                ("get_category_spend", {"category_id": 1}),
                ("get_supplier_scorecard", {"supplier_id": 1}),
                ("get_rfq_bid_matrix", {"rfq_id": "RFQ-001"}),
                ("get_contract_evidence", {"contract_id": "CTR-001-1"}),
            ]:
                result = await session.call_tool(name, args)
                assert not result.isError
                receipts.append({"tool": name, "passed": True})
            print(json.dumps({"protocol": "MCP stdio initialized", "checks": receipts}))


if __name__ == "__main__":
    asyncio.run(main())
