#!/usr/bin/env bash
# ─────────────────────────────────────────────────────────────────────────────
# start.sh  —  RunPod GPU startup
# Starts vLLM (Phi-3 Mini) then Streamlit dashboard
# Usage: bash start.sh
# ─────────────────────────────────────────────────────────────────────────────
set -e
cd "$(dirname "$0")"

echo "══════════════════════════════════════════════"
echo "  💰 Expense Tracker MCP Agent — RunPod Start"
echo "══════════════════════════════════════════════"

# ── 1. Dependencies ─────────────────────────────────────────────────────────
echo "📦 Installing Python dependencies…"
pip install -q -r requirements.txt

# ── 2. vLLM server ──────────────────────────────────────────────────────────
echo ""
echo "🚀 Starting vLLM with Phi-3 Mini…"
echo "   Model : microsoft/Phi-3-mini-4k-instruct"
echo "   Port  : 8000"
echo ""

python -m vllm.entrypoints.openai.api_server \
    --model microsoft/Phi-3-mini-4k-instruct \
    --trust-remote-code \
    --host 0.0.0.0 \
    --port 8000 \
    --max-model-len 4096 \
    --gpu-memory-utilization 0.85 \
    --dtype auto \
    &
VLLM_PID=$!
echo "  ✓ vLLM process started (PID $VLLM_PID)"

# ── 3. Wait for vLLM health ─────────────────────────────────────────────────
echo "⏳ Waiting for vLLM to be ready…"
WAITED=0
until curl -sf http://localhost:8000/health > /dev/null 2>&1; do
    sleep 4
    WAITED=$((WAITED+4))
    echo "   … ${WAITED}s elapsed"
    if [ $WAITED -gt 240 ]; then
        echo "⚠️  vLLM did not start in 4 min — Streamlit will run in regex-fallback mode"
        break
    fi
done
curl -sf http://localhost:8000/health > /dev/null 2>&1 && echo "  ✅ vLLM is ready!"

# ── 4. Streamlit ─────────────────────────────────────────────────────────────
echo ""
echo "🌐 Starting Streamlit on port 8501…"
echo "   URL: https://<pod-id>-8501.proxy.runpod.net"
echo ""

streamlit run app.py \
    --server.port 8501 \
    --server.address 0.0.0.0 \
    --server.headless true \
    --browser.gatherUsageStats false

# ── Cleanup ──────────────────────────────────────────────────────────────────
trap 'echo "Stopping vLLM…"; kill $VLLM_PID 2>/dev/null' EXIT
