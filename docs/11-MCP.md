# 11 — MCP (Model Context Protocol)

**Status: optional stretch goal.** The core app uses direct function calling and does not need MCP. Add MCP after the tool registry is stable.

## 1. Why add it

The analysis tools already have names, descriptions and Pydantic schemas. Wrapping the same registry as an MCP server lets any MCP-compatible client (Claude Desktop, IDEs, other agents) use your analyst: "profile this CSV", "run a Welch t-test". It shows the tools are cleanly separated from the web app.

## 2. Two roles

| Role | Meaning | Use here |
|------|---------|----------|
| **MCP server** | Exposes tools/resources to clients | Yes, expose the analysis tools |
| **MCP client** | Your agent consumes external tools | Not needed for MVP |

## 3. What to expose

**Tools** (from the registry): `profile_dataset`, `calculate_statistics`, `group_by_analysis`, `correlation_analysis`, `detect_outliers`, `statistical_test`, `generate_chart`, plus `list_datasets`.

**Resources** (read-only): `dataset://{id}/profile`, `analysis://{id}/findings`.

**Prompts** (optional): `investigate_dataset(dataset_id, question)`.

Do **not** expose: delete, auth, raw file download, or anything that executes arbitrary code.

## 4. Minimal server (Python SDK)

```python
# apps/api/app/mcp_server/server.py
from mcp.server.fastmcp import FastMCP
from app.tools.registry import REGISTRY, run_tool
from app.services.datasets import load_dataframe, get_profile

mcp = FastMCP("ai-data-analyst")

def register_tools():
    for spec in REGISTRY.values():
        # one MCP tool per registry entry; arguments validated by the same Pydantic model
        async def handler(**kwargs):
            return await run_tool(spec.name, kwargs, source="mcp")
        mcp.tool(name=spec.name, description=spec.description)(handler)

@mcp.resource("dataset://{dataset_id}/profile")
async def dataset_profile(dataset_id: str) -> dict:
    return await get_profile(dataset_id)

if __name__ == "__main__":
    register_tools()
    mcp.run()       # stdio for local clients
```

Check the current MCP SDK documentation for exact decorator signatures; they change between versions. Registering handlers in a loop also needs care with closures (bind `spec` as a default argument).

## 5. Transports

| Transport | Use |
|-----------|-----|
| stdio | Local clients such as Claude Desktop |
| Streamable HTTP | Remote/shared server, needs auth |

## 6. Client config (Claude Desktop example)

```json
{
  "mcpServers": {
    "ai-data-analyst": {
      "command": "python",
      "args": ["-m", "app.mcp_server.server"],
      "cwd": "/path/to/ai-data-analyst/apps/api",
      "env": { "DATABASE_URL": "postgresql+psycopg://...", "MCP_USER_ID": "<uuid>" }
    }
  }
}
```

## 7. Security rules

- Local stdio server runs as one fixed user (`MCP_USER_ID`); all calls pass the same ownership checks as the API.
- Remote HTTP server requires OAuth/bearer auth; never run it unauthenticated.
- Same limits: timeouts, row caps, argument validation, audit rows in `tool_executions` (with `source="mcp"`).
- Treat tool arguments from MCP clients as untrusted, exactly like LLM arguments.
- Return concise results; large payloads go through resources or file references.

## 8. Testing

- Use the MCP Inspector to list tools and call them manually.
- Test: unknown column → structured error; cross-user dataset → not found; oversized output → truncated with a pointer.

## 9. Build steps

1. Finish and test the registry (Week 2).
2. Add `source` field to `tool_executions`.
3. Write the MCP wrapper (≈1 day).
4. Verify with MCP Inspector, then Claude Desktop.
5. Document in README with a short demo GIF.

## 10. Do not confuse

- MCP is **not** needed for the LLM in your web app to call tools.
- MCP does not replace validation; it is just another entry point to the same safe registry.
