"""
agent.py  —  The MCP Agent
============================
This is the REAL agent loop:

  Step 1 — LLM receives user input + tool schemas
  Step 2 — LLM outputs a <tool_call> block
  Step 3 — Agent parses tool name + arguments from LLM output
  Step 4 — Agent calls the MCP server via MCPClient (real stdio MCP protocol)
  Step 5 — MCP server executes the tool and returns a result
  Step 6 — Agent feeds result back to LLM
  Step 7 — LLM produces a natural-language confirmation
  Step 8 — Agent returns confirmation + parsed data to Streamlit

The LLM is NOT hardcoded to know what to do — it reads the tool schemas
from the system prompt and decides which tool to call and with what arguments.

If the LLM (vLLM) is unavailable, the agent falls back to a regex parser
that still calls the MCP server (so the MCP path is always used).
"""

import asyncio
import json
import re
from datetime import date, timedelta

from mcp_client import MCPClient
from llm import llm_parse_transaction, llm_confirm, parse_tool_call, vllm_health


# ─────────────────────────────────────────────────────────────────────────────
# Regex fallback parser
# (Only used when vLLM is unreachable. Still calls MCP tools — not bypassed.)
# ─────────────────────────────────────────────────────────────────────────────

_INCOME_KW = ["salary", "income", "payment", "received", "business income", "client"]

_CATEGORY_MAP = {
    "Food & Groceries":      ["doodh","dudh","milk","bread","roti","sabzi","fruit",
                              "grocery","groceries","vegetable","atta","chawal","rice","aloo"],
    "Transportation":        ["petrol","fuel","uber","taxi","rickshaw","bus","transport",
                              "dlawaya","dalwaya"],
    "Dining":                ["restaurant","burger","biryani","khana","lunch","dinner",
                              "breakfast","cafe","pizza","paratha","chai"],
    "Housing":               ["rent","kiraya","ghar"],
    "Utilities":             ["bijli","electricity","gas","pani","water","internet",
                              "wifi","bill","phone"],
    "Health & Medical":      ["dawai","dawaai","medicine","doctor","hospital","health",
                              "clinic","pharmacy"],
    "Education & Learning":  ["school","fee","fees","tuition","books","education",
                              "university","college"],
    "Savings":               ["savings","bachat","save"],
    "Investments & Debt":    ["investment","invest","mutual","stocks","loan","debt"],
}


def _regex_parse(text: str) -> dict | None:
    t = text.lower()

    m = re.search(r"(\d[\d,]*(?:\.\d+)?)\s*(?:rs|rupees|pkr)?", t)
    if not m:
        return None

    amount = float(m.group(1).replace(",", ""))
    txn_type = "income" if any(k in t for k in _INCOME_KW) else "expense"

    category = "Income" if txn_type == "income" else "Other"
    if txn_type == "expense":
        for cat, kws in _CATEGORY_MAP.items():
            if any(k in t for k in kws):
                category = cat
                break

    txn_date = str(date.today())
    if "kal" in t or "yesterday" in t:
        txn_date = str(date.today() - timedelta(days=1))
    elif "parsun" in t or "day before" in t:
        txn_date = str(date.today() - timedelta(days=2))
    elif "peechlay haftay" in t or "last week" in t:
        txn_date = str(date.today() - timedelta(days=7))

    return {
        "name": "add_transaction",
        "arguments": {
            "description": text.strip()[:80],
            "category":    category,
            "type":        txn_type,
            "amount":      amount,
            "date":        txn_date,
            "raw_input":   text,
        },
    }


# ─────────────────────────────────────────────────────────────────────────────
# Core agent function
# ─────────────────────────────────────────────────────────────────────────────

async def _run_agent(user_text: str) -> dict:
    """
    Full MCP agent loop — always async.

    Returns:
        {
          "success":      bool,
          "message":      str,          # confirmation sentence for the UI
          "transaction":  dict | None,  # the parsed transaction data
          "used_llm":     bool,         # True = Phi-3 was used, False = regex fallback
        }
    """
    tool_call: dict | None = None
    used_llm = False

    # ── Step 1 & 2: Ask the LLM ──────────────────────────────────────────────
    if vllm_health():
        try:
            llm_output = llm_parse_transaction(user_text)
            tool_call  = parse_tool_call(llm_output)
            used_llm   = True
        except Exception as e:
            # vLLM responded but something went wrong — fall through to regex
            tool_call = None

    # ── Step 3: Fallback if LLM didn't produce a valid tool call ─────────────
    if tool_call is None:
        tool_call = _regex_parse(user_text)
        used_llm  = False

    if tool_call is None:
        return {
            "success":     False,
            "message":     "❌ Could not parse transaction. Please include an amount (e.g. 'lunch 500').",
            "transaction": None,
            "used_llm":    False,
        }

    tool_name = tool_call["name"]
    tool_args = tool_call.get("arguments", tool_call.get("args", {}))

    # ── Step 4 & 5: Call the MCP server ──────────────────────────────────────
    async with MCPClient() as mcp:
        tool_result_raw = await mcp.call_tool(tool_name, tool_args)

    tool_result = json.loads(tool_result_raw)

    if not tool_result.get("success", False):
        return {
            "success":     False,
            "message":     f"❌ Tool error: {tool_result.get('error', 'unknown')}",
            "transaction": None,
            "used_llm":    used_llm,
        }

    # ── Step 6 & 7: Feed result back to LLM for confirmation ─────────────────
    if used_llm:
        try:
            confirmation = llm_confirm(user_text, tool_result_raw)
        except Exception:
            confirmation = _default_confirmation(tool_args)
    else:
        confirmation = _default_confirmation(tool_args)

    return {
        "success":     True,
        "message":     f"✅ {confirmation}",
        "transaction": tool_args,
        "used_llm":    used_llm,
    }


def _default_confirmation(args: dict) -> str:
    sign = "+" if args.get("type") == "income" else "−"
    return (
        f"{args.get('description', 'Transaction')} recorded — "
        f"{sign} Rs {float(args.get('amount', 0)):,.0f} "
        f"[{args.get('category', 'Other')}]"
    )


# ─────────────────────────────────────────────────────────────────────────────
# Synchronous wrappers (called from Streamlit which is sync)
# ─────────────────────────────────────────────────────────────────────────────

def process_transaction(user_text: str) -> dict:
    """Sync wrapper for the async agent loop."""
    return asyncio.run(_run_agent(user_text))


def get_all_transactions() -> list:
    """Fetch all transactions via MCP."""
    async def _get():
        async with MCPClient() as mcp:
            raw = await mcp.call_tool("get_transactions", {})
            return json.loads(raw)
    return asyncio.run(_get())


def get_summary() -> dict:
    """Fetch summary via MCP."""
    async def _get():
        async with MCPClient() as mcp:
            raw = await mcp.call_tool("get_summary", {})
            return json.loads(raw)
    return asyncio.run(_get())