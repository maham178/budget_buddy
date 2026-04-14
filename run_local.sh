#!/bin/bash
# run_local.sh - Start everything locally with Ollama

echo "🚀 Starting MCP Budget Agent (Local Mode)"

# Check if Ollama is running
if ! curl -s http://localhost:11434/api/tags > /dev/null; then
    echo "⚠️ Ollama is not running. Please start Ollama first:"
    echo "   ollama serve"
    exit 1
fi

# Pull Phi-3 model if not present
if ! ollama list | grep -q "phi3:mini"; then
    echo "📦 Pulling phi3:mini model..."
    ollama pull phi3:mini
fi

# Set backend to ollama
export LLM_BACKEND=ollama
export OLLAMA_MODEL=phi3:mini

# Create data directory
mkdir -p data

# Run Streamlit
echo "🎨 Starting Streamlit dashboard..."
streamlit run app.py --server.port 8501 --server.address localhost