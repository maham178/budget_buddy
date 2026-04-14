"""
Configuration for MCP Budget Agent
Supports: Ollama (local), vLLM (production)
"""

import os
from pathlib import Path

class Config:
    # ========== BACKEND SELECTION ==========
    # Options: "ollama", "vllm", "mock"
    LLM_BACKEND = os.getenv("LLM_BACKEND", "ollama")  # Default to ollama for local testing
    
    # ========== OLLAMA CONFIGURATION (Local) ==========
    OLLAMA_API_URL = os.getenv("OLLAMA_API_URL", "http://localhost:11434/api/generate")
    OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "phi3:mini")  # phi3:mini, llama3, mistral
    OLLAMA_TIMEOUT = int(os.getenv("OLLAMA_TIMEOUT", "60"))
    
    # ========== vLLM CONFIGURATION (Production/RunPod) ==========
    VLLM_API_URL = os.getenv("VLLM_API_URL", "http://localhost:8000/v1/completions")
    VLLM_API_KEY = os.getenv("VLLM_API_KEY", "dummy")
    VLLM_TIMEOUT = int(os.getenv("VLLM_TIMEOUT", "60"))
    VLLM_MAX_TOKENS = int(os.getenv("VLLM_MAX_TOKENS", "500"))
    VLLM_TEMPERATURE = float(os.getenv("VLLM_TEMPERATURE", "0.1"))
    
    # ========== DATABASE (Works everywhere) ==========
    DATABASE_PATH = os.getenv("DATABASE_PATH", str(Path(__file__).parent / "data" / "budget.db"))
    
    # ========== APP SETTINGS ==========
    APP_NAME = "MCP Budget Agent"
    APP_ENV = os.getenv("APP_ENV", "development")  # development, production

config = Config()