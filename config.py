import os

class Config:
    # vLLM Configuration (runs locally on same pod)
    VLLM_API_URL = os.getenv("VLLM_API_URL", "http://localhost:8000/v1/completions")
    VLLM_API_KEY = os.getenv("VLLM_API_KEY", "dummy")
    VLLM_TIMEOUT = int(os.getenv("VLLM_TIMEOUT", "60"))
    VLLM_MAX_TOKENS = int(os.getenv("VLLM_MAX_TOKENS", "500"))
    VLLM_TEMPERATURE = float(os.getenv("VLLM_TEMPERATURE", "0.1"))
    
    # Database - Persistent storage on RunPod volume
    DATABASE_PATH = os.getenv("DATABASE_PATH", "/workspace/data/budget.db")
    
    # App
    APP_NAME = "MCP Budget Agent"
    APP_ENV = os.getenv("APP_ENV", "production")

config = Config()