#!/usr/bin/env bash
set -euo pipefail

echo "══════════════════════════════════════════════"
echo "  💰 Expense Tracker MCP Agent — RunPod Start"
echo "══════════════════════════════════════════════"

# ── 1. Install Python dependencies ───────────────────────────────────────────
echo "📦 Installing Python dependencies…"

# Step 1: Force-remove vLLM and all conflicting packages that the base image
# has pre-installed at wrong versions. We nuke them before reinstalling.
echo "   🧹 Purging stale packages…"
pip uninstall -y vllm transformers tokenizers accelerate 2>/dev/null || true
rm -rf /usr/local/lib/python3.11/dist-packages/vllm* 2>/dev/null || true
rm -rf /usr/local/lib/python3.11/dist-packages/transformers* 2>/dev/null || true
rm -rf /usr/local/lib/python3.11/dist-packages/tokenizers* 2>/dev/null || true
rm -rf /usr/local/lib/python3.11/dist-packages/accelerate* 2>/dev/null || true
echo "   ✓ Stale packages cleared"

# Step 2: Install exact pinned versions first (order matters — tokenizers
# must be installed BEFORE transformers so transformers sees the right version)
echo "   📌 Installing pinned versions…"
pip install \
    "tokenizers==0.21.1" \
    "transformers==4.51.3" \
    "accelerate==1.7.0" \
    --break-system-packages \
    --no-cache-dir \
    --force-reinstall \
    --quiet

# Step 3: Install everything else (vllm last — it pins its own deps)
echo "   📦 Installing remaining packages…"
pip install \
    "streamlit>=1.35.0" \
    "plotly>=5.20.0" \
    "pandas>=2.1.0" \
    "requests>=2.31.0" \
    "mcp>=1.0.0" \
    --break-system-packages \
    --no-cache-dir \
    --quiet

pip install \
    "vllm==0.8.5" \
    --break-system-packages \
    --no-cache-dir \
    --quiet

echo "✅ Dependencies installed"

# ── 2. Verify imports ────────────────────────────────────────────────────────
echo "🔍 Verifying installs…"
python - << 'PYCHECK'
import tokenizers, transformers, vllm
print(f"   tokenizers  : {tokenizers.__version__}")
print(f"   transformers: {transformers.__version__}")
print(f"   vllm        : {vllm.__version__}")
PYCHECK

# ── 3. Start vLLM ────────────────────────────────────────────────────────────
echo ""
echo "🚀 Starting vLLM with Phi-3 Mini…"
echo "   Model : microsoft/Phi-3-mini-4k-instruct"
echo "   Port  : 8000"
echo ""

HF_HUB_DISABLE_XET=1 python -m vllm.entrypoints.openai.api_server \
    --model microsoft/Phi-3-mini-4k-instruct \
    --host 0.0.0.0 \
    --port 8000 \
    --trust-remote-code \
    --dtype auto \
    --max-model-len 4096 \
    --gpu-memory-utilization 0.85 \
    --load-format safetensors \
    &

VLLM_PID=$!
echo "  ✓ vLLM process started (PID $VLLM_PID)"

# ── 4. Wait for vLLM to be ready ─────────────────────────────────────────────
echo "⏳ Waiting for vLLM to be ready…"
ELAPSED=0
MAX_WAIT=300

while [ $ELAPSED -lt $MAX_WAIT ]; do
    if ! kill -0 "$VLLM_PID" 2>/dev/null; then
        echo ""
        echo "❌ vLLM process exited unexpectedly (PID $VLLM_PID)."
        echo "   Check the logs above for the error."
        echo ""
        echo "🌐 Starting Streamlit in fallback mode on port 8501…"
        exec streamlit run app.py \
            --server.port 8501 \
            --server.address 0.0.0.0 \
            --server.headless true
    fi

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

# ── 5. Start Streamlit ───────────────────────────────────────────────────────
echo ""
echo "🌐 Starting Streamlit on port 8501…"
echo "   URL: https://<pod-id>-8501.proxy.runpod.net"
echo ""

exec streamlit run app.py \
    --server.port 8501 \
    --server.address 0.0.0.0 \
    --server.headless true