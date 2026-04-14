"""
MCP Budget Server - Model Context Protocol Implementation
"""

import json
import asyncio
from datetime import datetime
from typing import Any, Dict, List, Optional
import logging

from mcp.server import Server, NotificationOptions
from mcp.server.models import InitializationOptions
import mcp.server.stdio
import mcp.types as types

from config import config
from backend.db_handler import DatabaseHandler
from backend.llm_handler import LLMHandler
from backend.utils import format_currency

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Initialize handlers
db = DatabaseHandler(config.DATABASE_PATH)
llm = LLMHandler(
    api_url=config.VLLM_API_URL,
    api_key=config.VLLM_API_KEY,
    timeout=config.VLLM_TIMEOUT
)

# Create MCP server
server = Server("mcp-budget-server")

@server.list_tools()
async def handle_list_tools() -> List[types.Tool]:
    """List all available tools"""
    return [
        types.Tool(
            name="add_expense_natural",
            description="Add expenses using natural language",
            inputSchema={
                "type": "object",
                "properties": {
                    "text": {
                        "type": "string",
                        "description": "Natural language description of expenses"
                    }
                },
                "required": ["text"]
            }
        ),
        types.Tool(
            name="add_expense_structured",
            description="Add expense with structured data",
            inputSchema={
                "type": "object",
                "properties": {
                    "amount": {"type": "integer"},
                    "category": {"type": "string"},
                    "date": {"type": "string"},
                    "description": {"type": "string"}
                },
                "required": ["amount", "category", "date"]
            }
        ),
        types.Tool(
            name="get_monthly_summary",
            description="Get monthly spending summary",
            inputSchema={
                "type": "object",
                "properties": {
                    "year": {"type": "integer"},
                    "month": {"type": "integer"}
                }
            }
        ),
        types.Tool(
            name="check_budget",
            description="Check budget status for a category",
            inputSchema={
                "type": "object",
                "properties": {
                    "category": {"type": "string"}
                },
                "required": ["category"]
            }
        ),
        types.Tool(
            name="update_budget",
            description="Update budget for a category",
            inputSchema={
                "type": "object",
                "properties": {
                    "category": {"type": "string"},
                    "amount": {"type": "integer"}
                },
                "required": ["category", "amount"]
            }
        ),
        types.Tool(
            name="get_all_budgets",
            description="Get all category budgets",
            inputSchema={"type": "object", "properties": {}}
        )
    ]

@server.call_tool()
async def handle_call_tool(
    name: str, 
    arguments: Optional[Dict[str, Any]] = None
) -> List[types.TextContent]:
    """Execute tool calls"""
    
    try:
        if name == "add_expense_natural":
            text = arguments.get("text", "") if arguments else ""
            result = await handle_add_expense_natural(text)
            
        elif name == "add_expense_structured":
            result = await handle_add_expense_structured(arguments or {})
            
        elif name == "get_monthly_summary":
            year = arguments.get("year") if arguments else None
            month = arguments.get("month") if arguments else None
            result = await handle_monthly_summary(year, month)
            
        elif name == "check_budget":
            category = arguments.get("category") if arguments else ""
            result = await handle_check_budget(category)
            
        elif name == "update_budget":
            category = arguments.get("category") if arguments else ""
            amount = arguments.get("amount") if arguments else 0
            result = await handle_update_budget(category, amount)
            
        elif name == "get_all_budgets":
            result = await handle_get_all_budgets()
            
        else:
            result = {"error": f"Unknown tool: {name}"}
        
        return [types.TextContent(
            type="text",
            text=json.dumps(result, ensure_ascii=False)
        )]
        
    except Exception as e:
        logger.error(f"Tool execution error: {e}")
        return [types.TextContent(
            type="text",
            text=json.dumps({"error": str(e)})
        )]

async def handle_add_expense_natural(text: str) -> Dict:
    """Handle natural language expense addition"""
    expenses = llm.extract_expenses(text)
    
    if not expenses:
        return {
            "success": False,
            "message": "Could not extract expenses. Please specify amount clearly."
        }
    
    count = db.add_expenses_batch(expenses)
    
    # Check budget alerts
    alerts = []
    for expense in expenses:
        status = db.check_budget_status(expense['category'])
        if status['is_over']:
            alerts.append(f"{expense['category']} is over budget")
    
    return {
        "success": True,
        "expenses_added": count,
        "expenses": expenses,
        "alerts": alerts,
        "message": f"Added {count} expense(s)"
    }

async def handle_add_expense_structured(args: Dict) -> Dict:
    """Handle structured expense addition"""
    expense_id = db.add_expenses_batch([args])
    
    return {
        "success": True,
        "expense_id": expense_id,
        "message": f"Added expense: {format_currency(args['amount'])} for {args['category']}"
    }

async def handle_monthly_summary(year: Optional[int], month: Optional[int]) -> Dict:
    """Get monthly summary"""
    df = db.get_monthly_summary(year, month)
    
    if df.empty:
        return {
            "success": True,
            "has_data": False,
            "message": "No transactions found"
        }
    
    total = df['total_spent'].sum()
    
    return {
        "success": True,
        "has_data": True,
        "total_spent": total,
        "categories": df.to_dict('records'),
        "message": f"Total spent: {format_currency(total)}"
    }

async def handle_check_budget(category: str) -> Dict:
    """Check budget status"""
    status = db.check_budget_status(category)
    return {
        "success": True,
        **status,
        "message": f"{category}: {format_currency(status['spent'])} / {format_currency(status['budget'])}"
    }

async def handle_update_budget(category: str, amount: int) -> Dict:
    """Update budget"""
    if amount <= 0:
        return {"success": False, "message": "Budget must be positive"}
    
    success = db.update_budget(category, amount)
    
    return {
        "success": success,
        "category": category,
        "new_budget": amount,
        "message": f"Updated {category} budget to {format_currency(amount)}" if success else "Update failed"
    }

async def handle_get_all_budgets() -> Dict:
    """Get all budgets"""
    categories = db.get_categories()
    return {
        "success": True,
        "categories": categories,
        "message": f"Found {len(categories)} categories"
    }

@server.list_resources()
async def handle_list_resources() -> List[types.Resource]:
    """List available resources"""
    return [
        types.Resource(
            uri="budget://summary",
            name="Current Month Summary",
            description="Spending summary for current month",
            mimeType="application/json"
        ),
        types.Resource(
            uri="budget://alerts",
            name="Budget Alerts",
            description="Current budget overages",
            mimeType="application/json"
        )
    ]

@server.read_resource()
async def handle_read_resource(uri: str) -> str:
    """Read resource content"""
    if uri == "budget://summary":
        summary = await handle_monthly_summary(None, None)
        return json.dumps(summary, ensure_ascii=False)
    elif uri == "budget://alerts":
        df = db.get_monthly_summary()
        alerts = []
        if not df.empty:
            for _, row in df.iterrows():
                if row['total_spent'] > row['budget']:
                    alerts.append({
                        "category": row['category'],
                        "overspent": row['total_spent'] - row['budget']
                    })
        return json.dumps(alerts, ensure_ascii=False)
    else:
        raise ValueError(f"Unknown resource: {uri}")

async def main():
    """Run MCP server"""
    async with mcp.server.stdio.stdio_server() as (read_stream, write_stream):
        await server.run(
            read_stream,
            write_stream,
            InitializationOptions(
                server_name="mcp-budget-server",
                server_version="1.0.0",
                capabilities=server.get_capabilities(
                    notification_options=NotificationOptions(),
                    experimental_capabilities={},
                ),
            ),
        )

if __name__ == "__main__":
    asyncio.run(main())