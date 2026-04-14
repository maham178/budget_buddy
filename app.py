"""
MCP Budget Agent - Modern Dashboard UI
Works with Ollama (local) and vLLM (production)
"""

import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime
import os

from backend.utils import format_currency
from backend.db_handler import DatabaseHandler
from backend.llm_handler import LLMHandler
from config import config

# Page configuration
st.set_page_config(
    page_title="MCP Budget Agent",
    page_icon="💰",
    layout="wide"
)

# Custom CSS
st.markdown("""
<style>
    .metric-card {
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        padding: 1rem;
        border-radius: 1rem;
        color: white;
        margin: 0.5rem 0;
    }
    .metric-card h3 { margin: 0; font-size: 0.9rem; opacity: 0.9; }
    .metric-card .value { font-size: 2rem; font-weight: bold; margin: 0.5rem 0; }
    .section-header {
        font-size: 1.3rem;
        font-weight: 600;
        margin: 1rem 0 0.5rem 0;
        padding-bottom: 0.5rem;
        border-bottom: 2px solid #e0e0e0;
    }
    .transaction-card {
        background: white;
        border-radius: 0.5rem;
        padding: 0.75rem;
        margin: 0.5rem 0;
        box-shadow: 0 1px 3px rgba(0,0,0,0.1);
        border-left: 4px solid;
    }
    .transaction-title { font-weight: 600; font-size: 1rem; }
    .transaction-desc { font-size: 0.8rem; color: #666; margin-top: 0.25rem; }
    .transaction-amount { font-weight: bold; text-align: right; color: #dc2626; }
    .transaction-category {
        font-size: 0.7rem;
        padding: 0.2rem 0.5rem;
        border-radius: 1rem;
        background: #f0f0f0;
        display: inline-block;
    }
    .backend-badge {
        position: fixed;
        bottom: 10px;
        right: 10px;
        background: #f0f0f0;
        padding: 0.25rem 0.75rem;
        border-radius: 1rem;
        font-size: 0.7rem;
        font-family: monospace;
    }
</style>
""", unsafe_allow_html=True)

# Initialize database and LLM
@st.cache_resource
def init_agent():
    db = DatabaseHandler(config.DATABASE_PATH)
    
    # Use configured backend
    if config.LLM_BACKEND == "ollama":
        llm = LLMHandler(
            backend="ollama",
            api_url=config.OLLAMA_API_URL,
            model=config.OLLAMA_MODEL,
            timeout=config.OLLAMA_TIMEOUT
        )
    elif config.LLM_BACKEND == "vllm":
        llm = LLMHandler(
            backend="vllm",
            api_url=config.VLLM_API_URL,
            api_key=config.VLLM_API_KEY,
            timeout=config.VLLM_TIMEOUT
        )
    else:
        llm = LLMHandler(backend="mock")
    
    return db, llm

db, llm = init_agent()

# Show backend info
backend_display = {
    "ollama": f"🦙 Ollama ({config.OLLAMA_MODEL})",
    "vllm": "⚡ vLLM (Production)",
    "mock": "🎭 Mock (Testing)"
}
st.markdown(f'<div class="backend-badge">{backend_display.get(config.LLM_BACKEND, config.LLM_BACKEND)}</div>', unsafe_allow_html=True)

# Header
st.markdown('<p style="font-size: 2rem; font-weight: bold; margin-bottom: 0;">💰 MCP Budget Agent</p>', unsafe_allow_html=True)
st.caption("Model Context Protocol | Smart Budget Tracking")

# Income and expense summary
col1, col2, col3 = st.columns(3)

with col1:
    st.markdown("""
    <div class="metric-card">
        <h3>📊 Total Income</h3>
        <div class="value">Rs 50,000</div>
    </div>
    """, unsafe_allow_html=True)

with col2:
    summary = db.get_monthly_summary()
    total_expenses = summary['total_spent'].sum() if not summary.empty else 0
    
    st.markdown(f"""
    <div class="metric-card">
        <h3>💸 Total Expenses</h3>
        <div class="value">Rs {total_expenses:,.0f}</div>
    </div>
    """, unsafe_allow_html=True)

with col3:
    balance = 50000 - total_expenses
    st.markdown(f"""
    <div class="metric-card">
        <h3>💵 Balance</h3>
        <div class="value">Rs {balance:,.0f}</div>
    </div>
    """, unsafe_allow_html=True)

# Add Transaction Section
st.markdown('<div class="section-header">➕ ADD TRANSACTION</div>', unsafe_allow_html=True)

col_input, col_btn = st.columns([4, 1])
with col_input:
    transaction_text = st.text_input(
        "",
        placeholder='e.g., "kal doodh liya 150 rs" or "petrol 4000"',
        label_visibility="collapsed",
        key="transaction_input"
    )
with col_btn:
    if st.button("🚀 Add", type="primary", use_container_width=True):
        if transaction_text:
            with st.spinner("Processing with LLM..."):
                expenses = llm.extract_expenses(transaction_text)
                if expenses:
                    count = db.add_expenses_batch(expenses)
                    st.success(f"✅ Added {count} expense(s)!")
                    st.rerun()
                else:
                    st.error("Could not extract expenses. Please specify amount clearly.")
        else:
            st.warning("Please enter a transaction")

# Two column layout
col_chart1, col_chart2 = st.columns(2)

with col_chart1:
    st.markdown('<div class="section-header">📊 SPENDING BY CATEGORY</div>', unsafe_allow_html=True)
    
    if not summary.empty:
        fig = go.Figure()
        fig.add_trace(go.Bar(
            x=summary['total_spent'],
            y=summary['category'],
            orientation='h',
            marker=dict(color=summary['total_spent'], colorscale='Reds', showscale=False),
            text=summary['total_spent'].apply(lambda x: f'Rs {x:,.0f}'),
            textposition='outside'
        ))
        fig.update_layout(height=350, margin=dict(l=0, r=0, t=0, b=0))
        st.plotly_chart(fig, use_container_width=True)
    else:
        st.info("No expenses yet. Add some transactions!")

with col_chart2:
    st.markdown('<div class="section-header">📈 WEEKLY TREND</div>', unsafe_allow_html=True)
    
    # Get last 4 weeks of data
    weekly_data = []
    for i in range(4):
        week_start = datetime.now() - timedelta(weeks=i+1)
        week_end = datetime.now() - timedelta(weeks=i)
        # Simplified - in production, query actual weekly data
        weekly_data.append(random.randint(1000, 5000))
    
    weeks = ['Week 4', 'Week 3', 'Week 2', 'Week 1']
    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=weeks,
        y=weekly_data[::-1],
        mode='lines+markers',
        line=dict(color='#667eea', width=3),
        marker=dict(size=10, color='#764ba2'),
        fill='tozeroy',
        fillcolor='rgba(102, 126, 234, 0.2)'
    ))
    fig.update_layout(height=350, margin=dict(l=0, r=0, t=0, b=0))
    st.plotly_chart(fig, use_container_width=True)

# Recent Transactions
st.markdown('<div class="section-header">📋 RECENT TRANSACTIONS</div>', unsafe_allow_html=True)

category_colors = {
    'groceries': '#10b981', 'transport': '#3b82f6', 'utilities': '#f59e0b',
    'healthcare': '#ef4444', 'dining': '#8b5cf6', 'entertainment': '#ec4899',
    'shopping': '#06b6d4', 'other': '#6b7280'
}

transactions = db.get_transactions(limit=10)
if not transactions.empty:
    for _, trans in transactions.iterrows():
        category = trans['category']
        color = category_colors.get(category, '#6b7280')
        
        st.markdown(f"""
        <div class="transaction-card" style="border-left-color: {color};">
            <div style="display: flex; justify-content: space-between; align-items: center;">
                <div>
                    <span class="transaction-title">{trans.get('description', 'Transaction')[:30]}</span>
                    <div class="transaction-desc">{trans['date']} - "{trans.get('raw_text', trans.get('description', ''))[:40]}"</div>
                    <span class="transaction-category" style="background: {color}20; color: {color};">{category.title()}</span>
                </div>
                <div class="transaction-amount">-Rs {trans['amount']:,.0f}</div>
            </div>
        </div>
        """, unsafe_allow_html=True)
else:
    st.info("No transactions yet. Add some using the form above!")

# Quick actions
st.markdown("---")
col_q1, col_q2, col_q3, col_q4 = st.columns(4)

quick_actions = {
    "🍎 Add Grocery": "grocery 500",
    "⛽ Add Petrol": "petrol 3000",
    "🍕 Add Food": "dinner 1000",
    "💊 Add Medicine": "medicine 500"
}

for col, (label, text) in zip([col_q1, col_q2, col_q3, col_q4], quick_actions.items()):
    with col:
        if st.button(label, use_container_width=True):
            st.session_state['transaction_input'] = text
            st.rerun()

# Footer
st.markdown("---")
st.caption(f"🔧 MCP Architecture | Backend: {backend_display.get(config.LLM_BACKEND, config.LLM_BACKEND)} | Database: SQLite")