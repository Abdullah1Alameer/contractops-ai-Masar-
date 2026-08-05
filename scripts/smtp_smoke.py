#!/usr/bin/env python3
"""Send one non-confidential SMTP verification message."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from app.services.email_delivery import (  # noqa: E402
    EmailDeliveryError,
    send_email,
    validate_email_configuration,
)


def main() -> int:
    parser = argparse.ArgumentParser(description="Verify configured SMTP delivery")
    parser.add_argument("--to", required=True, help="Recipient mailbox")
    args = parser.parse_args()

    try:
        validate_email_configuration()
        result = send_email(
            recipient=args.to,
            subject="ContractOps AI SMTP verification",
            text_body="This is a non-confidential SMTP delivery verification message.",
            html_body="<p>This is a non-confidential SMTP delivery verification message.</p>",
        )
        print(json.dumps({"status": result.status, "code": result.safe_error_code}))
        return 0 if result.status == "sent" else 1
    except EmailDeliveryError as exc:
        print(json.dumps({"status": "failed", "code": exc.code}))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
