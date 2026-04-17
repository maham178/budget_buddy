"""
app.py  —  Streamlit Dashboard
================================
Calls agent.py which runs the real MCP agent loop.
"""

import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go

from agent import process_transaction, get_all_transactions, get_summary
from llm import vllm_health

# ─────────────────────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="💰 Expense Tracker",
    page_icon="💰",
    layout="wide",
    initial_sidebar_state="collapsed",
)

# ─────────────────────────────────────────────────────────────────────────────
# CSS
# ─────────────────────────────────────────────────────────────────────────────
st.markdown("""
<style>
[data-testid="stAppViewContainer"] {
    background: #0d0f1a; color: #e2e4f0;
    font-family: 'Segoe UI', system-ui, sans-serif;
}
[data-testid="stHeader"] { background: transparent; }
[data-testid="stSidebar"] { background: #111320; }

/* metric cards */
.mcard {
    background: linear-gradient(135deg,#141728 0%,#1c1f35 100%);
    border: 1px solid #252945; border-radius: 18px;
    padding: 22px 20px; text-align: center;
    box-shadow: 0 6px 24px rgba(0,0,0,.45);
}
.mlabel { font-size:.72rem; color:#676b96; text-transform:uppercase; letter-spacing:1.3px; margin-bottom:8px; }
.mvalue { font-size:1.6rem; font-weight:700; letter-spacing:-.5px; }
.inc { color:#4ade80; } .exp { color:#f87171; }
.bal { color:#60a5fa; } .sav { color:#c084fc; }

/* input */
[data-testid="stTextInput"] input {
    background:#141728 !important; color:#e2e4f0 !important;
    border:1px solid #353868 !important; border-radius:14px !important;
    padding:14px 18px !important; font-size:1rem !important;
}
[data-testid="stTextInput"] input:focus {
    border-color:#6366f1 !important;
    box-shadow:0 0 0 3px rgba(99,102,241,.18) !important;
}

/* button */
.stButton>button {
    background:linear-gradient(135deg,#6366f1,#8b5cf6) !important;
    color:#fff !important; border:none !important;
    border-radius:14px !important; padding:13px 26px !important;
    font-size:1rem !important; font-weight:600 !important;
    width:100% !important; transition:opacity .2s !important;
}
.stButton>button:hover { opacity:.82 !important; }

/* badges */
.badge {
    display:inline-block; border-radius:20px;
    padding:4px 12px; font-size:.75rem; font-weight:600;
}
.badge-llm  { background:rgba(99,102,241,.18); color:#818cf8; border:1px solid #4f52b2; }
.badge-rgx  { background:rgba(251,191,36,.14); color:#fbbf24; border:1px solid #92630f; }
.badge-mcp  { background:rgba(52,211,153,.14); color:#34d399; border:1px solid #0f6b4a; }

/* txn cards */
.txn {
    background:#141728; border-radius:14px;
    padding:13px 16px; margin-bottom:10px;
    border-left:4px solid; display:flex;
    justify-content:space-between; align-items:center;
}
.txn-i { border-color:#4ade80; } .txn-e { border-color:#f87171; }
.txn-sub { font-size:.8rem; color:#676b96; margin-top:3px; }
.txn-amt-i { color:#4ade80; font-weight:700; font-size:1rem; }
.txn-amt-e { color:#f87171; font-weight:700; font-size:1rem; }

/* section */
.sec { font-size:1rem; font-weight:600; color:#b0b4d8;
       margin:22px 0 10px 0; padding-bottom:8px;
       border-bottom:1px solid #252945; }

/* hints */
.hrow { display:flex; flex-wrap:wrap; gap:8px; margin:10px 0 16px 0; }
.hchip {
    background:#141728; border:1px solid #353868;
    border-radius:20px; padding:5px 13px;
    font-size:.75rem; color:#676b96; font-style:italic;
}

/* alert */
.ok  { background:rgba(74,222,128,.10); border:1px solid #4ade80;
       border-radius:12px; padding:12px 16px; color:#4ade80; font-size:.93rem; margin:8px 0; }
.err { background:rgba(248,113,113,.10); border:1px solid #f87171;
       border-radius:12px; padding:12px 16px; color:#f87171; font-size:.93rem; margin:8px 0; }
</style>
""", unsafe_allow_html=True)

# ─────────────────────────────────────────────────────────────────────────────
PLOTLY_BASE = dict(
    paper_bgcolor="rgba(0,0,0,0)",
    plot_bgcolor="rgba(0,0,0,0)",
    font=dict(color="#b0b4d8", family="Segoe UI"),
    margin=dict(l=8, r=8, t=28, b=8),
)
PALETTE = ["#818cf8","#c084fc","#f472b6","#fb923c",
           "#4ade80","#38bdf8","#facc15","#34d399","#e879f9","#f87171"]

CAT_ICON = {
    "Food & Groceries":"🛒","Transportation":"🚗","Dining":"🍽️",
    "Housing":"🏠","Utilities":"💡","Health & Medical":"💊",
    "Education & Learning":"📚","Savings":"🏦",
    "Investments & Debt":"📈","Income":"💵","Other":"📌",
}

def fmt(n: float) -> str:
    return f"Rs {n:,.0f}"


# ─────────────────────────────────────────────────────────────────────────────
# App
# ─────────────────────────────────────────────────────────────────────────────
def main():
    # ── header ──
    llm_up = vllm_health()
    st.markdown(f"""
    <div style='text-align:center;padding:18px 0 6px 0'>
      <span style='font-size:2.1rem;font-weight:800;
                   background:linear-gradient(90deg,#6366f1,#a78bfa,#f472b6);
                   -webkit-background-clip:text;-webkit-text-fill-color:transparent;'>
        💰 Expense Tracker
      </span>
      <p style='color:#4b4f72;font-size:.85rem;margin-top:5px;'>
        Phi-3 Mini · MCP Agent · vLLM · Streamlit
        &nbsp;&nbsp;
        <span class='badge {"badge-llm" if llm_up else "badge-rgx"}'>
          {"🟢 LLM online" if llm_up else "🟡 LLM offline — regex mode"}
        </span>
      </p>
    </div>
    """, unsafe_allow_html=True)

    # ── live data ──
    summary = get_summary()
    txns    = get_all_transactions()
    income  = summary["total_income"]
    expenses= summary["total_expenses"]
    balance = summary["balance"]
    by_cat  = summary.get("by_category", {})

    # ── metric cards ──
    c1,c2,c3,c4 = st.columns(4)
    for col, label, val, cls in [
        (c1, "Total Income",     income,       "inc"),
        (c2, "Total Expenses",   expenses,     "exp"),
        (c3, "Balance",          balance,      "bal"),
        (c4, "Emergency Fund ≈", income*0.20,  "sav"),
    ]:
        col.markdown(f"""
        <div class='mcard'>
          <div class='mlabel'>{label}</div>
          <div class='mvalue {cls}'>{fmt(val)}</div>
        </div>""", unsafe_allow_html=True)

    st.markdown("<div style='height:20px'></div>", unsafe_allow_html=True)

    # ── input ──
    st.markdown("<div class='sec'>📝 Add Transaction</div>", unsafe_allow_html=True)
    st.markdown("""
    <div class='hrow'>
      <span class='hchip'>kal doodh liya 150 rs</span>
      <span class='hchip'>petrol 3000</span>
      <span class='hchip'>salary 75000 received</span>
      <span class='hchip'>bijli bill 2200</span>
      <span class='hchip'>medicines 1000</span>
      <span class='hchip'>school fees 4000</span>
      <span class='hchip'>business income 150000</span>
      <span class='hchip'>peechlay haftay petrol dlawaya 3000</span>
    </div>""", unsafe_allow_html=True)

    ci, cb = st.columns([5,1])
    with ci:
        user_input = st.text_input(
            label="",
            placeholder="What did you spend or earn? (English or Roman Urdu)",
            key="txn_input",
            label_visibility="collapsed",
        )
    with cb:
        clicked = st.button("Add ➕", use_container_width=True)

    if clicked and user_input.strip():
        with st.spinner("🤖 Agent thinking…"):
            result = process_transaction(user_input.strip())

        if result["success"]:
            mode = (
                '<span class="badge badge-llm">Phi-3 Mini</span>'
                if result["used_llm"]
                else '<span class="badge badge-rgx">Regex</span>'
            )
            st.markdown(
                f"<div class='ok'>"
                f"{result['message']}&nbsp;&nbsp;{mode}&nbsp;"
                f'<span class="badge badge-mcp">MCP ✓</span>'
                f"</div>",
                unsafe_allow_html=True,
            )
            st.rerun()
        else:
            st.markdown(f"<div class='err'>{result['message']}</div>", unsafe_allow_html=True)

    elif clicked:
        st.markdown("<div class='err'>Please type something first.</div>", unsafe_allow_html=True)

    # ── charts ──
    if txns:
        df = __import__("pandas").DataFrame(txns)
        df["date"] = __import__("pandas").to_datetime(df["date"])

        left, right = st.columns([3,2])

        with left:
            if by_cat:
                st.markdown("<div class='sec'>📊 Spending by Category</div>", unsafe_allow_html=True)
                cat_df = __import__("pandas").DataFrame(
                    list(by_cat.items()), columns=["Category","Amount"]
                ).sort_values("Amount")
                fig = px.bar(
                    cat_df, x="Amount", y="Category",
                    orientation="h", color="Category",
                    color_discrete_sequence=PALETTE, text="Amount",
                )
                fig.update_traces(
                    texttemplate="Rs %{text:,.0f}",
                    textposition="outside",
                    marker_line_width=0,
                )
                fig.update_layout(
                    **PLOTLY_BASE, showlegend=False, height=300,
                    xaxis=dict(visible=False),
                    yaxis=dict(showgrid=False),
                )
                st.plotly_chart(fig, use_container_width=True, config={"displayModeBar":False})

            st.markdown("<div class='sec'>🥧 Income vs Expenses</div>", unsafe_allow_html=True)
            if income > 0 or expenses > 0:
                fig2 = go.Figure(go.Pie(
                    labels=["Income","Expenses"],
                    values=[income, expenses],
                    hole=0.56,
                    marker_colors=["#4ade80","#f87171"],
                    textinfo="label+percent",
                    textfont_color="#e2e4f0",
                ))
                fig2.add_annotation(
                    text=f"<b>{fmt(balance)}</b>",
                    x=0.5, y=0.5, showarrow=False,
                    font=dict(size=15, color="#60a5fa"),
                )
                fig2.update_layout(
                    **PLOTLY_BASE, height=240, showlegend=True,
                    legend=dict(orientation="h", y=-0.08),
                )
                st.plotly_chart(fig2, use_container_width=True, config={"displayModeBar":False})

        with right:
            st.markdown("<div class='sec'>🕒 Recent Transactions</div>", unsafe_allow_html=True)
            for t in txns[:12]:
                ic = CAT_ICON.get(t["category"],"💳")
                cls  = "txn-i" if t["type"]=="income" else "txn-e"
                acls = "txn-amt-i" if t["type"]=="income" else "txn-amt-e"
                sign = "+" if t["type"]=="income" else "−"
                st.markdown(f"""
                <div class='txn {cls}'>
                  <div>
                    <div style='font-weight:600;color:#e2e4f0;'>{ic} {t['category']}</div>
                    <div class='txn-sub'>{str(t['description'])[:52]}</div>
                    <div class='txn-sub'>{t['date']}</div>
                  </div>
                  <div class='{acls}'>{sign} Rs {float(t['amount']):,.0f}</div>
                </div>""", unsafe_allow_html=True)

        # ── full table ──
        st.markdown("<div class='sec'>📋 All Transactions</div>", unsafe_allow_html=True)
        tbl = df[["date","description","category","type","amount"]].copy()
        tbl["date"]   = tbl["date"].dt.strftime("%Y-%m-%d")
        tbl["amount"] = tbl["amount"].apply(lambda x: f"Rs {x:,.0f}")
        tbl.columns   = ["Date","Description","Category","Type","Amount"]

        def _color(v):
            return "color:#4ade80;font-weight:600" if v=="income" else "color:#f87171;font-weight:600"

        st.dataframe(
            tbl.style
               .applymap(_color, subset=["Type"])
               .set_properties(**{"background-color":"#141728","color":"#c7caed","border-color":"#252945"})
               .set_table_styles([{"selector":"th","props":[
                   ("background-color","#1c1f35"),("color","#676b96"),
                   ("font-size","0.77rem"),("text-transform","uppercase"),
               ]}]),
            use_container_width=True,
            hide_index=True,
        )
    else:
        st.markdown("""
        <div style='text-align:center;padding:70px 0;color:#2d3154;'>
          <div style='font-size:3rem;'>💸</div>
          <div style='margin-top:12px;font-size:1.05rem;'>
            No transactions yet — add your first one above!
          </div>
        </div>""", unsafe_allow_html=True)

    st.markdown("""
    <div style='text-align:center;padding:28px 0 6px;color:#2d3154;font-size:.77rem;'>
      Phi-3 Mini · vLLM (port 8000) · MCP stdio · SQLite · Streamlit · RunPod
    </div>""", unsafe_allow_html=True)


if __name__ == "__main__":
    main()
