# 💰 Expense Tracker — Genuine MCP Agent LLM Project

## How It Actually Works (Verified)

```
User types: "kal doodh liya 150 rs"
       │
       ▼
┌─────────────────────────────────────────────────────────┐
│  app.py  (Streamlit)                                    │
│  Calls agent.process_transaction(user_text)             │
└───────────────────────┬─────────────────────────────────┘
                        │
                        ▼
┌─────────────────────────────────────────────────────────┐
│  agent.py  — The MCP Agent Loop                         │
│                                                         │
│  STEP 1: Check if vLLM is reachable                     │
│  STEP 2: If yes → llm.llm_parse_transaction(text)       │
│          Sends Phi-3 prompt with tool schemas           │
│          Phi-3 outputs <tool_call>{...}</tool_call>      │
│  STEP 3: llm.parse_tool_call() extracts name + args     │
│          (if LLM offline → regex fallback, same steps)  │
│                                                         │
│  STEP 4: async with MCPClient() as mcp:                 │
│              result = await mcp.call_tool(name, args)   │
│          ← THIS IS THE REAL MCP PROTOCOL CALL           │
│                                                         │
│  STEP 5: If LLM was used → llm.llm_confirm()           │
│          Feeds tool result back, gets confirmation       │
│                                                         │
│  STEP 6: Returns {success, message, transaction, used_llm}│
└───────────────────────┬─────────────────────────────────┘
                        │  real MCP stdio protocol
                        ▼
┌─────────────────────────────────────────────────────────┐
│  mcp_client.py  — MCPClient                             │
│  Opens subprocess: python mcp_server.py                 │
│  Communicates via MCP stdio protocol (JSON-RPC)         │
│  Uses mcp.ClientSession from the official MCP SDK       │
└───────────────────────┬─────────────────────────────────┘
                        │  subprocess stdio
                        ▼
┌─────────────────────────────────────────────────────────┐
│  mcp_server.py  — FastMCP Server                        │
│  @mcp.tool() add_transaction(...)                       │
│  @mcp.tool() get_summary()                              │
│  @mcp.tool() get_transactions()                         │
│  mcp.run(transport="stdio")                             │
└───────────────────────┬─────────────────────────────────┘
                        │
                        ▼
                  expenses.db (SQLite)
```

## File Roles

| File | Role |
|------|------|
| `mcp_server.py` | MCP Server subprocess. Exposes 3 tools via FastMCP. Only file that touches the DB. |
| `mcp_client.py` | MCP Client. Starts `mcp_server.py` as subprocess, connects via stdio, wraps `ClientSession`. |
| `llm.py` | All Phi-3 Mini / vLLM logic. Builds correct `<|user|>` prompt format, calls `/v1/completions`, parses `<tool_call>` tags. |
| `agent.py` | The agent loop. Calls LLM → parses tool call → calls MCP → feeds result back to LLM → returns confirmation. |
| `app.py` | Streamlit UI. Calls `agent.py`. Shows live mode badge (LLM/regex + MCP ✓). |

## What Makes This a Real MCP Agent

1. **Real MCP server** — `mcp_server.py` runs as a subprocess using `FastMCP` from the official `mcp` Python SDK
2. **Real MCP client** — `mcp_client.py` uses `mcp.ClientSession` + `stdio_client` — the standard MCP transport
3. **Real agent loop** — LLM decides tool/args → agent calls MCP → result fed back to LLM
4. **LLM is not hardcoded** — Phi-3 reads tool schemas from the prompt and decides what to call
5. **Every DB write goes through MCP** — even when LLM is offline, the regex fallback still calls the MCP server

## Phi-3 Prompt Format

Phi-3 Mini uses its own special tokens — NOT OpenAI ChatML format:

```
<s><|user|>
{system prompt with tool schemas}

User input: kal doodh liya 150 rs<|end|>
<|assistant|>
```

The model responds with:
```
<tool_call>
{"name": "add_transaction", "arguments": {"description": "doodh purchase", "amount": 150, ...}}
</tool_call>
```

## RunPod Deployment

```
Recommended GPU : RTX 4090 or A40 (24 GB VRAM)
Base image      : runpod/pytorch:2.2.0-py3.10-cuda12.1.1-devel-ubuntu22.04
Expose ports    : 8000 (vLLM), 8501 (Streamlit)
Disk            : 30 GB+
```

```bash
# On RunPod instance
git clone <your-repo> && cd expense_tracker_v2
bash start.sh
```

Dashboard: `https://<pod-id>-8501.proxy.runpod.net`

## Graceful Degradation

If vLLM hasn't loaded yet:
- The dashboard shows a **🟡 LLM offline — regex mode** badge
- Transactions still work via the regex parser
- All DB writes still go through the MCP server
- Once vLLM is ready, the app automatically switches to **🟢 LLM online**
- No restart needed
