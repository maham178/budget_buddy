#!/usr/bin/env bash
set -euo pipefail

echo "══════════════════════════════════════════════"
echo "  💰 Expense Tracker MCP Agent — RunPod Start"
echo "══════════════════════════════════════════════"

# ── 1. Install Python dependencies ───────────────────────────────────────────
echo "📦 Installing Python dependencies…"

# ── Step 1: Purge stale ML packages ──────────────────────────────────────────
echo "   🧹 Purging stale packages…"
pip uninstall -y vllm transformers tokenizers accelerate 2>/dev/null || true

# Also nuke any leftover dist-packages to avoid ghost imports
for pkg in vllm transformers tokenizers accelerate; do
    rm -rf /usr/local/lib/python3.*/dist-packages/${pkg}* 2>/dev/null || true
    rm -rf /usr/local/lib/python3.*/dist-packages/${pkg}-*.dist-info 2>/dev/null || true
done
echo "   ✓ Stale ML packages cleared"

# ── Step 2: Fix blinker — distutils-installed version blocks streamlit ────────
# pip cannot uninstall distutils packages normally; we delete the files manually
# then reinstall with --ignore-installed so the new egg-info is pip-managed.
echo "   🩹 Patching distutils-installed blinker…"
python - << 'PYBLINKER'
import importlib, pathlib, shutil, sys

try:
    import blinker
    loc = pathlib.Path(blinker.__file__).parent
    print(f"      Found blinker at: {loc}")
    # Remove the package directory
    shutil.rmtree(str(loc), ignore_errors=True)
    # Remove any egg-info / dist-info sitting next to it
    for p in loc.parent.glob("blinker*"):
        if p.is_dir():
            shutil.rmtree(str(p), ignore_errors=True)
        else:
            p.unlink(missing_ok=True)
    print("      Removed old blinker files ✓")
except ImportError:
    print("      blinker not present — nothing to patch")
PYBLINKER

# Now install the pip-managed version cleanly
pip install "blinker>=1.7" \
    --break-system-packages \
    --no-cache-dir \
    --ignore-installed \
    --quiet
echo "   ✓ blinker patched"

# ── Step 3: Install pinned ML versions ───────────────────────────────────────
# tokenizers MUST come before transformers so transformers sees the right version.
echo "   📌 Installing pinned ML versions…"
pip install \
    "tokenizers==0.21.1" \
    "transformers==4.51.3" \
    "accelerate==1.7.0" \
    --break-system-packages \
    --no-cache-dir \
    --force-reinstall \
    --quiet
echo "   ✓ ML versions installed"

# ── Step 4: Install app dependencies ─────────────────────────────────────────
# Use --ignore-installed for streamlit so the patched blinker isn't blocked.
# The torchaudio/torchvision torch-version warnings are harmless (they ship with
# the base image and we are NOT touching torch itself).
echo "   📦 Installing app packages…"
pip install \
    "streamlit>=1.35.0" \
    "plotly>=5.20.0" \
    "pandas>=2.1.0" \
    "requests>=2.31.0" \
    "mcp>=1.0.0" \
    --break-system-packages \
    --no-cache-dir \
    --ignore-installed \
    --quiet 2>&1 | grep -v "^WARNING\|^DEPRECATION\|^notice" || true
echo "   ✓ App packages installed"

# ── Step 5: Install vLLM (last — it pins its own deps) ───────────────────────
echo "   🚀 Installing vLLM 0.8.5…"
pip install \
    "vllm==0.8.5" \
    --break-system-packages \
    --no-cache-dir \
    --quiet 2>&1 | grep -v "^WARNING\|^DEPRECATION\|^notice" || true
echo "   ✓ vLLM installed"

echo "✅ All dependencies installed"

# ── 2. Verify imports ────────────────────────────────────────────────────────
echo ""
echo "🔍 Verifying installs…"
python - << 'PYCHECK'
import sys

ok = True
checks = [
    ("tokenizers",    "tokenizers"),
    ("transformers",  "transformers"),
    ("vllm",          "vllm"),
    ("streamlit",     "streamlit"),
    ("mcp",           "mcp"),
]

for label, mod in checks:
    try:
        m = __import__(mod)
        ver = getattr(m, "__version__", "?")
        print(f"   ✓ {label:<14}: {ver}")
    except ImportError as e:
        print(f"   ✗ {label:<14}: MISSING — {e}", file=sys.stderr)
        ok = False

if not ok:
    sys.exit(1)
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