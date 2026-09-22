"""Environment-based provider configuration."""

import os
import json
from pathlib import Path
from dotenv import load_dotenv


ROOT = Path(__file__).resolve().parent
env_path = ROOT /".env"
load_dotenv(env_path)


MODEL_PROVIDER = os.getenv("MODEL_PROVIDER")
MODEL_NAME = os.getenv("MODEL_NAME")
API_KEY = os.getenv("GEMINI_API_KEY")
OLLAMA_HOST = os.getenv("OLLAMA_HOST", "http://localhost:11434")


INBOX_PATH = ROOT / "data" / "inbox.json"
OUTBOX_PATH = ROOT / "outbox"
OUTPUT_PATH = ROOT / "output"


# =========================================================
# LOAD INBOX
# =========================================================

def load_inbox():

    with open(INBOX_PATH,"r",encoding="utf-8") as f:
        return json.load(f)


