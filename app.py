"""
MCP Budget Agent - Streamlit Dashboard
"""

import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime
import json
import subprocess
import sys

from backend.utils import format_currency

st.set_page_config(
    page_title="MCP Budget Agent",
    page_icon="💰",
    layout="wide"
)

# Custom CSS
st.markdown("""
    <style>
    .main-header { font-size: 2.5rem; font-weight: bold; color: #1E88E5; text-align: center; }
    .mcp-badge { background-color: #f0f2f6; padding: 0.5rem; border-radius: 0.5rem; text-align: center; }
    </style>
""", unsafe_allow_html=True)

# Header
st.markdown('<p class="main-header">💰 MCP Budget Agent</p>', unsafe_allow_html=True)
st.markdown('<div class="mcp-badge">🔌 Model Context Protocol (MCP) Compliant</div>', unsafe_allow_html=True)

# Initialize MCP client connection
@st.cache_resource
def get_mcp_client():
    """Simple MCP client using subprocess"""
    import mcp.client.stdio
    import anyio
    
    class SimpleMCPClient:
        def __init__(self):
            self.process = None
            
        def call_tool(self, tool_name, arguments=None):
            # For simplicity, directly call database
            from backend.db_handler import DatabaseHandler
            from backend.llm_handler import LLMHandler
            from config import config
            
            self.db = DatabaseHandler(config.DATABASE_PATH)
            self.llm = LLMHandler(config.VLLM_API_URL, config.VLLM_API_KEY)
            
            if tool_name == "add_expense_natural":
                text = arguments.get("text", "")
                expenses = self.llm.extract_expenses(text)
                if expenses:
                    count = self.db.add_expenses_batch(expenses)
                    return {"success": True, "message": f"Added {count} expenses", "expenses": expenses}
                return {"success": False, "message": "No expenses extracted"}
            
            elif tool_name == "get_monthly_summary":
                df = self.db.get_monthly_summary()
                if df.empty:
                    return {"has_data": False, "message": "No data"}
                return {"has_data": True, "total_spent": df['total_spent'].sum(), "categories": df.to_dict('records')}
            
            elif tool_name == "check_budget":
                category = arguments.get("category")
                return self.db.check_budget_status(category)
            
            elif tool_name == "update_budget":
                category = arguments.get("category")
                amount = arguments.get("amount")
                success = self.db.update_budget(category, amount)
                return {"success": success, "message": f"Updated {category} to {format_currency(amount)}"}
            
            elif tool_name == "get_all_budgets":
                return {"categories": self.db.get_categories()}
            
            return {"error": "Unknown tool"}
    
    return SimpleMCPClient()

mcp = get_mcp_client()

# Sidebar
with st.sidebar:
    st.header("🛠️ MCP Tools Available")
    st.markdown("""
    - `add_expense_natural` - Natural language expenses
    - `add_expense_structured` - Structured expense entry
    - `get_monthly_summary` - Monthly spending report
    - `check_budget` - Check category budget
    - `update_budget` - Update budget limits
    - `get_all_budgets` - List all budgets
    """)
    
    st.markdown("---")
    st.subheader("📊 Quick Stats")
    
    # Show budget summary
    budgets = mcp.call_tool("get_all_budgets")
    if budgets.get("categories"):
        for cat in budgets["categories"][:5]:
            st.caption(f"• {cat['name']}: {format_currency(cat['budget'])}")

# Main input
col1, col2 = st.columns([2, 1])

with col1:
    st.subheader("💬 Natural Language Input")
    user_input = st.text_area(
        "Describe your expenses:",
        placeholder="Example: grocery 5000, petrol 3000, dinner 1200",
        height=100
    )
    
    if st.button("🚀 Process with MCP Agent", type="primary"):
        if user_input:
            with st.spinner("Agent processing..."):
                result = mcp.call_tool("add_expense_natural", {"text": user_input})
                if result.get("success"):
                    st.success(f"✅ {result['message']}")
                    if result.get("expenses"):
                        with st.expander("📋 Extracted Expenses"):
                            st.json(result["expenses"])
                else:
                    st.error(result.get("message", "Failed to process"))
        else:
            st.warning("Please enter some text")

with col2:
    st.subheader("📝 Quick Examples")
    examples = [
        "grocery 5000",
        "petrol 3000, coffee 500",
        "dinner 1500, movie 800"
    ]
    for ex in examples:
        if st.button(f"📌 {ex}", key=ex):
            st.session_state['user_input'] = ex
            st.rerun()

# Dashboard
st.markdown("---")
st.header("📊 Financial Dashboard")

# Load data
summary = mcp.call_tool("get_monthly_summary")

if summary.get("has_data"):
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("💰 Total Spent", format_currency(summary["total_spent"]))
    
    # Budget vs Actual Chart
    st.subheader("📈 Budget vs Actual")
    df = pd.DataFrame(summary["categories"])
    
    fig = go.Figure()
    fig.add_trace(go.Bar(x=df['category'], y=df['total_spent'], name='Actual', marker_color='indianred'))
    fig.add_trace(go.Bar(x=df['category'], y=df['budget'], name='Budget', marker_color='lightgrey'))
    fig.update_layout(barmode='group', height=400)
    st.plotly_chart(fig, use_container_width=True)
    
    # Spending by category pie chart
    st.subheader("🎯 Spending Distribution")
    fig_pie = px.pie(values=df['total_spent'], names=df['category'], title="Expenses by Category")
    st.plotly_chart(fig_pie, use_container_width=True)
    
    # Budget alerts
    st.subheader("⚠️ Budget Alerts")
    for _, row in df.iterrows():
        if row['total_spent'] > row['budget']:
            st.error(f"❌ {row['category'].title()}: {format_currency(row['total_spent'])} / {format_currency(row['budget'])}")
        elif row['total_spent'] > row['budget'] * 0.8:
            st.warning(f"⚠️ {row['category'].title()}: {format_currency(row['total_spent'])} / {format_currency(row['budget'])} (80% used)")
else:
    st.info("📭 No transactions yet. Add some expenses using the form above!")

# Footer
st.markdown("---")
st.caption("🔧 MCP Architecture | vLLM Backend | Model Context Protocol")