"""Configuration and environment settings for the PragMind Agentic Hub."""

import os
from dotenv import load_dotenv

load_dotenv()

# LLM Configuration
MODEL_NAME = os.getenv("MODEL_NAME", "gpt-4o")
MAX_TOKENS = int(os.getenv("MAX_TOKENS", "4096"))
FORGE_MAX_TOKENS = int(os.getenv("FORGE_MAX_TOKENS", "16000"))

# API Configuration
API_HOST = os.getenv("API_HOST", "0.0.0.0")
API_PORT = int(os.getenv("API_PORT", "8000"))

# CORS Configuration
CORS_ORIGINS = os.getenv("CORS_ORIGINS", "*").split(",")

# Logging
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")
