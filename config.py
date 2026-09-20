"""Environment-based provider configuration."""

import os
from pathlib import Path
from dotenv import load_dotenv


ROOT = Path(__file__).resolve().parent
env_path = ROOT /".env"
load_dotenv(env_path)


MODEL_PROVIDER = os.getenv("MODEL_PROVIDER")
MODEL_NAME = os.getenv("MODEL_NAME")
# API_KEY = os.getenv("GEMINI_API_KEY")
OLLAMA_HOST = os.getenv("OLLAMA_HOST", "http://localhost:11434")


INBOX_PATH = ROOT / "data" / "inbox.json"
OUTBOX_PATH = ROOT / "outbox"




# SYSTEM_PROMPT = """You are FlightOps, an airline operations officer.
# Use tools when operational data is needed. Never invent database facts.
# When a tool fails, explain the failure plainly and continue if possible.
# For complex operational questions, use all relevant tools before concluding.
# """
