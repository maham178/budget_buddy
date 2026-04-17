"""
mcp_server.py  —  The MCP Server
=================================
Runs as a SUBPROCESS. The agent connects to it via stdio.
Exposes 3 tools:
  • add_transaction
  • get_transactions
  • get_summary

This is the ONLY place that touches the database.
"""

import sqlite3
import json
from pathlib import Path
from datetime import date as _date

from mcp.server.fastmcp import FastMCP

# ── DB path sits next to this file ──────────────────────────────────────────
DB_PATH = Path(__file__).parent / "expenses.db"

# ── FastMCP instance ─────────────────────────────────────────────────────────
mcp = FastMCP("expense-tracker")


# ── Database init ─────────────────────────────────────────────────────────────
def _init_db() -> None:
    conn = sqlite3.connect(DB_PATH)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS transactions (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            date        TEXT    NOT NULL,
            description TEXT    NOT NULL,
            category    TEXT    NOT NULL,
            type        TEXT    NOT NULL CHECK(type IN ('income','expense')),
            amount      REAL    NOT NULL,
            raw_input   TEXT    DEFAULT ''
        )
    """)
    conn.commit()
    conn.close()


_init_db()


# ── Tool 1 ────────────────────────────────────────────────────────────────────
@mcp.tool()
def add_transaction(
    description: str,
    category: str,
    type: str,
    amount: float,
    date: str,
    raw_input: str = "",
) -> str:
    """
    Add a financial transaction to the database.

    Args:
        description: Short human-readable description (max 80 chars)
        category:    One of: Food & Groceries | Transportation | Dining |
                     Housing | Utilities | Health & Medical |
                     Education & Learning | Savings | Investments & Debt |
                     Income | Other
        type:        'income' or 'expense'
        amount:      Positive number in PKR (no sign)
        date:        ISO date string YYYY-MM-DD
        raw_input:   The original text the user typed (optional)

    Returns:
        JSON string with {"success": true, "id": <row_id>}
    """
    if type not in ("income", "expense"):
        return json.dumps({"success": False, "error": "type must be income or expense"})
    if amount <= 0:
        return json.dumps({"success": False, "error": "amount must be positive"})

    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute(
        "INSERT INTO transactions (date, description, category, type, amount, raw_input) "
        "VALUES (?, ?, ?, ?, ?, ?)",
        (date, description[:80], category, type, float(amount), raw_input),
    )
    row_id = c.lastrowid
    conn.commit()
    conn.close()
    return json.dumps({"success": True, "id": row_id})


# ── Tool 2 ────────────────────────────────────────────────────────────────────
@mcp.tool()
def get_transactions() -> str:
    """
    Retrieve all transactions from the database, newest first.

    Returns:
        JSON array of transaction objects.
    """
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    rows = [
        dict(r)
        for r in conn.execute(
            "SELECT * FROM transactions ORDER BY date DESC, id DESC"
        ).fetchall()
    ]
    conn.close()
    return json.dumps(rows)


# ── Tool 3 ────────────────────────────────────────────────────────────────────
@mcp.tool()
def get_summary() -> str:
    """
    Return aggregate totals: income, expenses, balance, and per-category breakdown.

    Returns:
        JSON object with total_income, total_expenses, balance, by_category dict.
    """
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    income   = c.execute("SELECT COALESCE(SUM(amount),0) FROM transactions WHERE type='income'").fetchone()[0]
    expenses = c.execute("SELECT COALESCE(SUM(amount),0) FROM transactions WHERE type='expense'").fetchone()[0]
    cat_rows = c.execute(
        "SELECT category, SUM(amount) FROM transactions WHERE type='expense' "
        "GROUP BY category ORDER BY 2 DESC"
    ).fetchall()
    conn.close()

    return json.dumps({
        "total_income":   income,
        "total_expenses": expenses,
        "balance":        income - expenses,
        "by_category":    {row[0]: row[1] for row in cat_rows},
    })


# ── Entry point ───────────────────────────────────────────────────────────────
if __name__ == "__main__":
    mcp.run(transport="stdio")
