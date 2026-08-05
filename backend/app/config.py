import os
from pathlib import Path

from dotenv import load_dotenv

# repo root: backend/app/config.py -> parents[2] == contractops/
ROOT = Path(__file__).resolve().parents[2]
load_dotenv(ROOT / ".env")

DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://postgres:postgres@localhost:5432/contractops")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
AI_MODEL = os.getenv("AI_MODEL", "gpt-4o")
DEMO_TOKEN = os.getenv("DEMO_TOKEN", "demo-secret-token")
STORAGE_DIR = os.getenv("STORAGE_DIR", str(ROOT / "storage"))
MAX_UPLOAD_MB = 20
DEMO_CONTRACTS_DIR = ROOT / "database" / "demo_contracts"
GROUND_TRUTH_PATH = ROOT / "database" / "seed" / "ground_truth.json"
REVIEW_BASE_URL = os.getenv("REVIEW_BASE_URL", "http://localhost:3000")
ESIGN_PROVIDER = os.getenv("ESIGN_PROVIDER", "simulated").strip().lower()
EMAIL_PROVIDER = os.getenv("EMAIL_PROVIDER", "simulated").strip().lower()
