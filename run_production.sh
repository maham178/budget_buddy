#!/bin/bash
# run_production.sh - For RunPod deployment with vLLM

echo "🚀 Starting MCP Budget Agent (Production Mode)"

# Set backend to vLLM
export LLM_BACKEND=vllm
export VLLM_API_URL=http://localhost:8000/v1/completions

# Create data directory
mkdir -p /workspace/data

# Start vLLM (if not already running)
if ! curl -s http://localhost:8000/health > /dev/null; then
    echo "📡 Starting vLLM server..."
    python -m vllm.entrypoints.openai.api_server \
        --model microsoft/phi-2 \
        --port 8000 \
        --max-model-len 2048 \
        --gpu-memory-utilization 0.85 &
    
    echo "⏳ Waiting for vLLM to load (60 seconds)..."
    sleep 60
fi

# Run Streamlit
echo "🎨 Starting Streamlit dashboard..."
streamlit run app.py --server.port 7860 --server.address 0.0.0.0