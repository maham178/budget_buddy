"""
llm.py  —  Phi-3 Mini via vLLM
================================
Handles:
  • Building the correct Phi-3 prompt format  (<|user|> / <|assistant|> tags)
  • Injecting tool schemas into the prompt so the model knows what tools exist
  • Calling the vLLM /v1/completions endpoint
  • Parsing <tool_call> JSON from the model's response
  • Producing a natural-language confirmation after a tool result is known
"""

import json
import re
from datetime import date, timedelta

import requests

# ── vLLM config ───────────────────────────────────────────────────────────────
VLLM_URL   = "http://localhost:8000/v1/completions"
MODEL_NAME = "microsoft/Phi-3-mini-4k-instruct"
TIMEOUT    = 60          # seconds


# ── Phi-3 special tokens ──────────────────────────────────────────────────────
# Phi-3 Mini uses these exact tokens; do NOT use ChatML or OpenAI format.
BOS  = "<s>"
EOS  = "<|end|>"
USER = "<|user|>"
ASST = "<|assistant|>"


# ── Tool schema injected into the system prompt ───────────────────────────────
# We describe tools in plain text — Phi-3 Mini understands this better than
# JSON schema notation because it was trained on Hermes-style prompts.

TOOL_DOCS = """
You have access to these tools. To call a tool, output EXACTLY this format and nothing else:

<tool_call>
{"name": "<tool_name>", "arguments": {<args as JSON>}}
</tool_call>

Available tools:

1. add_transaction(description, category, type, amount, date, raw_input)
   - description : short text (e.g. "milk purchase")
   - category    : one of [Food & Groceries, Transportation, Dining, Housing,
                   Utilities, Health & Medical, Education & Learning,
                   Savings, Investments & Debt, Income, Other]
   - type        : "income" or "expense"
   - amount      : positive number (PKR, no sign)
   - date        : YYYY-MM-DD
   - raw_input   : the user's original text

2. get_summary()  — returns totals (call with no arguments: {})

3. get_transactions()  — returns all rows (call with no arguments: {})
"""


def _system_prompt() -> str:
    today     = date.today()
    yesterday = today - timedelta(days=1)
    parsun    = today - timedelta(days=2)
    last_week = today - timedelta(days=7)

    return f"""You are a bilingual (English + Roman Urdu) personal finance assistant.
Today's date: {today.isoformat()}

{TOOL_DOCS}

Date interpretation rules:
- "kal" / "yesterday"         → {yesterday.isoformat()}
- "parsun" / "day before"     → {parsun.isoformat()}
- "peechlay haftay"/"last week" → {last_week.isoformat()}
- no date mentioned           → {today.isoformat()}

Category rules (Roman Urdu → category):
- doodh/milk/bread/roti/sabzi/fruit/atta/chawal → Food & Groceries
- petrol/fuel/uber/taxi/rickshaw/bus            → Transportation
- restaurant/burger/biryani/khana/lunch/dinner  → Dining
- rent/kiraya                                   → Housing
- bijli/electricity/gas/pani/internet/bill      → Utilities
- dawai/dawaai/medicine/doctor/hospital         → Health & Medical
- school/fee/fees/tuition/books                 → Education & Learning
- savings/bachat                                → Savings
- investment/mutual fund/stocks/loan            → Investments & Debt
- salary/income/business income/payment/received → Income (type=income)

CRITICAL RULES:
1. When a user describes a transaction, call add_transaction immediately.
2. Output ONLY the <tool_call> block. No explanation before or after.
3. After you receive the tool result, write ONE short confirmation sentence."""


def _build_prompt(user_text: str, tool_result: str | None = None) -> str:
    """
    Build the full Phi-3 prompt string.

    Turn 1 (no tool result yet):
      <s><|user|>system + user_text<|end|><|assistant|>

    Turn 2 (after tool was called, feed result back):
      … <tool_result>…</tool_result><|end|><|user|>Confirm.<|end|><|assistant|>
    """
    system = _system_prompt()

    if tool_result is None:
        # First turn: ask the model to parse the transaction
        prompt = (
            f"{BOS}{USER}\n"
            f"{system}\n\n"
            f"User input: {user_text}{EOS}"
            f"{ASST}\n"
        )
    else:
        # Second turn: feed tool result back, ask for confirmation
        prompt = (
            f"{BOS}{USER}\n"
            f"{system}\n\n"
            f"User input: {user_text}{EOS}"
            f"{ASST}\n"
            f"<tool_call_result>\n{tool_result}\n</tool_call_result>{EOS}"
            f"{USER}\nGive a brief 1-sentence confirmation in the same language as the user's input.{EOS}"
            f"{ASST}\n"
        )
    return prompt


def _call_vllm(prompt: str, max_tokens: int = 256) -> str:
    """Send prompt to vLLM and return generated text."""
    payload = {
        "model":       MODEL_NAME,
        "prompt":      prompt,
        "max_tokens":  max_tokens,
        "temperature": 0.0,
        "stop":        [EOS, USER, "<|end|>"],
    }
    resp = requests.post(VLLM_URL, json=payload, timeout=TIMEOUT)
    resp.raise_for_status()
    data = resp.json()
    return data["choices"][0]["text"].strip()


def parse_tool_call(text: str) -> dict | None:
    """
    Extract tool call from model output.
    Looks for:  <tool_call> {...} </tool_call>
    Returns dict with keys 'name' and 'arguments', or None.
    """
    m = re.search(r"<tool_call>\s*(\{.*?\})\s*</tool_call>", text, re.DOTALL)
    if m:
        try:
            return json.loads(m.group(1))
        except json.JSONDecodeError:
            pass
    return None


# ── Public API ────────────────────────────────────────────────────────────────

def llm_parse_transaction(user_text: str) -> str:
    """
    Pass user text to Phi-3 Mini (Turn 1).
    Returns the raw model output — may contain a <tool_call> block.
    Raises requests.RequestException if vLLM is unreachable.
    """
    prompt = _build_prompt(user_text)
    return _call_vllm(prompt, max_tokens=256)


def llm_confirm(user_text: str, tool_result: str) -> str:
    """
    Pass the tool result back to Phi-3 Mini (Turn 2).
    Returns a natural-language confirmation sentence.
    """
    prompt = _build_prompt(user_text, tool_result=tool_result)
    return _call_vllm(prompt, max_tokens=80)


def vllm_health() -> bool:
    """Return True if vLLM server is reachable."""
    try:
        r = requests.get("http://localhost:8000/health", timeout=3)
        return r.status_code == 200
    except Exception:
        return False
