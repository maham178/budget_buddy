#!/usr/bin/env bash
set -euo pipefail

echo "══════════════════════════════════════════════"
echo "  💰 Expense Tracker MCP Agent — RunPod Start"
echo "══════════════════════════════════════════════"

# ── 1. Install Python dependencies ───────────────────────────────────────────
echo "📦 Installing Python dependencies…"

# Install everything from requirements.txt first
pip install -r requirements.txt \
    --break-system-packages \
    --ignore-installed blinker \
    --quiet

# Pin tokenizers AFTER vLLM install — vLLM may pull a newer one as a side-effect
# tokenizers==0.22.2 is required for vLLM 0.8.5 + transformers 4.46.x compatibility
pip install "tokenizers==0.22.2" \
    --break-system-packages \
    --force-reinstall \
    --quiet

echo "✅ Dependencies installed"

# ── 2. Start vLLM ────────────────────────────────────────────────────────────
echo ""
echo "🚀 Starting vLLM with Phi-3 Mini…"
echo "   Model : microsoft/Phi-3-mini-4k-instruct"
echo "   Port  : 8000"
echo ""

python -m vllm.entrypoints.openai.api_server \
    --model microsoft/Phi-3-mini-4k-instruct \
    --host 0.0.0.0 \
    --port 8000 \
    --trust-remote-code \
    --dtype auto \
    --max-model-len 4096 \
    --gpu-memory-utilization 0.85 \
    &

VLLM_PID=$!
echo "  ✓ vLLM process started (PID $VLLM_PID)"

# ── 3. Wait for vLLM to be ready ─────────────────────────────────────────────
echo "⏳ Waiting for vLLM to be ready…"
ELAPSED=0
MAX_WAIT=300   # 5 minutes

while [ $ELAPSED -lt $MAX_WAIT ]; do
    # Check if the process died early — fail fast instead of waiting 5 min
    if ! kill -0 "$VLLM_PID" 2>/dev/null; then
        echo ""
        echo "❌ vLLM process exited unexpectedly (PID $VLLM_PID)."
        echo "   Check the logs above for the error."
        echo "   Common cause: tokenizers/transformers version mismatch."
        echo ""
        echo "🌐 Starting Streamlit in fallback mode on port 8501…"
        exec streamlit run app.py \
            --server.port 8501 \
            --server.address 0.0.0.0 \
            --server.headless true
    fi

    # Try the health endpoint
    if curl -sf http://localhost:8000/health > /dev/null 2>&1; then
        echo ""
        echo "✅ vLLM is ready!"
        break
    fi

    sleep 4
    ELAPSED=$((ELAPSED + 4))
    echo "   … ${ELAPSED}s elapsed"
done

if [ $ELAPSED -ge $MAX_WAIT ]; then
    echo ""
    echo "⚠️  vLLM did not respond in ${MAX_WAIT}s — starting Streamlit in fallback mode"
fi

# ── 4. Start Streamlit ───────────────────────────────────────────────────────
echo ""
echo "🌐 Starting Streamlit on port 8501…"
echo "   URL: https://<pod-id>-8501.proxy.runpod.net"
echo ""

exec streamlit run app.py \
    --server.port 8501 \
    --server.address 0.0.0.0 \
    --server.headless true