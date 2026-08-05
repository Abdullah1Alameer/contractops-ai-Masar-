import os
from dataclasses import dataclass, field
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


@dataclass(frozen=True)
class EmailDeliverySettings:
    app_env: str
    enabled: str
    host: str
    port: str
    username: str
    password: str = field(repr=False)
    from_email: str
    from_name: str
    use_tls: str
    use_ssl: str
    timeout_seconds: str
    public_app_url: str
    portal_token_secret: str = field(repr=False)


def get_email_delivery_settings() -> EmailDeliverySettings:
    """Read SMTP settings at call time so runtime overrides are honored."""
    return EmailDeliverySettings(
        app_env=os.getenv("APP_ENV", "local").strip().lower(),
        enabled=os.getenv("EMAIL_DELIVERY_ENABLED", "false").strip().lower(),
        host=os.getenv("SMTP_HOST", "").strip(),
        port=os.getenv("SMTP_PORT", "587").strip(),
        username=os.getenv("SMTP_USERNAME", "").strip(),
        password=os.getenv("SMTP_PASSWORD", ""),
        from_email=os.getenv("SMTP_FROM_EMAIL", "").strip(),
        from_name=os.getenv("SMTP_FROM_NAME", "ContractOps AI").strip(),
        use_tls=os.getenv("SMTP_USE_TLS", "true").strip().lower(),
        use_ssl=os.getenv("SMTP_USE_SSL", "false").strip().lower(),
        timeout_seconds=os.getenv("SMTP_TIMEOUT_SECONDS", "10").strip(),
        public_app_url=os.getenv("PUBLIC_APP_URL", "").strip(),
        portal_token_secret=os.getenv("PORTAL_TOKEN_SECRET", ""),
    )
