"""Safe SMTP delivery boundary for review and signature emails."""
from __future__ import annotations

import ipaddress
import math
import re
import smtplib
import ssl
from dataclasses import dataclass, field
from datetime import datetime, timezone
from email.message import EmailMessage
from email.utils import formataddr, parseaddr
from typing import Callable
from urllib.parse import urlsplit

from app.config import EmailDeliverySettings, get_email_delivery_settings


MAX_SMTP_TIMEOUT_SECONDS = 60.0
LOCAL_PART_PATTERN = re.compile(
    r"^[A-Za-z0-9!#$%&'*+/=?^_`{|}~-]+(?:\.[A-Za-z0-9!#$%&'*+/=?^_`{|}~-]+)*$"
)
DOMAIN_LABEL_PATTERN = re.compile(r"^[A-Za-z0-9](?:[A-Za-z0-9-]{0,61}[A-Za-z0-9])?$")


class EmailDeliveryError(Exception):
    """Deterministic configuration or input error without secret details."""

    def __init__(self, status_code: int, code: str):
        self.status_code = status_code
        self.code = code
        super().__init__(code)

    def __repr__(self) -> str:
        return f"EmailDeliveryError(status_code={self.status_code}, code={self.code!r})"


@dataclass(frozen=True)
class EmailDeliveryResult:
    status: str
    provider_message_id: str | None
    safe_error_code: str | None
    sent_at: datetime | None


@dataclass(frozen=True)
class _ValidatedEmailConfiguration:
    host: str
    port: int
    username: str = field(repr=False)
    password: str = field(repr=False)
    from_email: str
    from_name: str
    use_tls: bool
    use_ssl: bool
    timeout_seconds: float


def _parse_bool(value: str) -> bool:
    if value == "true":
        return True
    if value == "false":
        return False
    raise EmailDeliveryError(500, "smtp_configuration_invalid")


def _is_local_hostname(hostname: str | None) -> bool:
    if not hostname:
        return True
    normalized = hostname.rstrip(".").lower()
    if normalized == "localhost" or normalized.endswith(".localhost"):
        return True
    try:
        return ipaddress.ip_address(normalized).is_loopback
    except ValueError:
        return False


def validate_recipient(recipient: str) -> str:
    """Return one normalized mailbox or raise a deterministic safe error."""
    if not isinstance(recipient, str) or not recipient.strip():
        raise EmailDeliveryError(422, "invalid_email_recipient")
    if any(character in recipient for character in ("\r", "\n", ",", ";")):
        raise EmailDeliveryError(422, "invalid_email_recipient")
    display_name, address = parseaddr(recipient)
    if display_name or address != recipient.strip():
        raise EmailDeliveryError(422, "invalid_email_recipient")
    local, separator, domain = address.rpartition("@")
    labels = domain.split(".")
    if (
        not separator
        or len(address) > 254
        or len(local) > 64
        or not LOCAL_PART_PATTERN.fullmatch(local)
        or len(domain) > 253
        or len(labels) < 2
        or any(not DOMAIN_LABEL_PATTERN.fullmatch(label) for label in labels)
    ):
        raise EmailDeliveryError(422, "invalid_email_recipient")
    return address


def _validate_public_url(settings: EmailDeliverySettings) -> None:
    if settings.app_env not in {"demo", "production"}:
        return
    parsed = urlsplit(settings.public_app_url)
    if parsed.scheme != "https" or _is_local_hostname(parsed.hostname):
        raise EmailDeliveryError(500, "public_app_url_invalid")


def _load_validated_email_configuration() -> _ValidatedEmailConfiguration:
    settings = get_email_delivery_settings()
    enabled = _parse_bool(settings.enabled)
    if not enabled:
        raise EmailDeliveryError(503, "email_delivery_disabled")

    required = (
        settings.host,
        settings.port,
        settings.from_email,
        settings.portal_token_secret,
    )
    if any(not value for value in required):
        raise EmailDeliveryError(500, "smtp_configuration_missing")

    try:
        port = int(settings.port)
        use_tls = _parse_bool(settings.use_tls)
        use_ssl = _parse_bool(settings.use_ssl)
    except (TypeError, ValueError):
        raise EmailDeliveryError(500, "smtp_configuration_invalid") from None
    try:
        timeout_seconds = float(settings.timeout_seconds)
    except (TypeError, ValueError):
        raise EmailDeliveryError(500, "smtp_timeout_invalid") from None

    if not 1 <= port <= 65535:
        raise EmailDeliveryError(500, "smtp_configuration_invalid")
    if (
        not math.isfinite(timeout_seconds)
        or timeout_seconds <= 0
        or timeout_seconds > MAX_SMTP_TIMEOUT_SECONDS
    ):
        raise EmailDeliveryError(500, "smtp_timeout_invalid")
    if use_tls and use_ssl:
        raise EmailDeliveryError(500, "smtp_tls_ssl_conflict")
    if bool(settings.username) != bool(settings.password):
        raise EmailDeliveryError(500, "smtp_configuration_missing")

    validate_recipient(settings.from_email)
    _validate_public_url(settings)
    return _ValidatedEmailConfiguration(
        host=settings.host,
        port=port,
        username=settings.username,
        password=settings.password,
        from_email=settings.from_email,
        from_name=settings.from_name,
        use_tls=use_tls,
        use_ssl=use_ssl,
        timeout_seconds=timeout_seconds,
    )


def validate_email_configuration() -> None:
    """Validate current environment without returning secret configuration."""
    _load_validated_email_configuration()


def _failed(code: str) -> EmailDeliveryResult:
    return EmailDeliveryResult(
        status="failed",
        provider_message_id=None,
        safe_error_code=code,
        sent_at=None,
    )


def send_email(
    *,
    recipient: str,
    subject: str,
    text_body: str,
    html_body: str,
    smtp_factory: Callable[..., object] | None = None,
) -> EmailDeliveryResult:
    """Validate and send one multipart email, returning safe metadata only."""
    configuration = _load_validated_email_configuration()
    recipient = validate_recipient(recipient)
    if (
        not isinstance(subject, str)
        or not subject.strip()
        or "\r" in subject
        or "\n" in subject
        or not isinstance(text_body, str)
        or not text_body.strip()
        or not isinstance(html_body, str)
        or not html_body.strip()
    ):
        raise EmailDeliveryError(422, "invalid_email_content")

    message = EmailMessage()
    message["To"] = recipient
    message["From"] = formataddr((configuration.from_name, configuration.from_email))
    message["Subject"] = subject
    message.set_content(text_body)
    message.add_alternative(html_body, subtype="html")

    factory = smtp_factory or (smtplib.SMTP_SSL if configuration.use_ssl else smtplib.SMTP)
    tls_context = ssl.create_default_context()
    connection_options = {"timeout": configuration.timeout_seconds}
    if configuration.use_ssl:
        connection_options["context"] = tls_context
    try:
        client = factory(
            configuration.host,
            configuration.port,
            **connection_options,
        )
    except Exception:
        return _failed("smtp_connection_failed")

    phase = "connection"
    try:
        if configuration.use_tls:
            client.starttls(context=tls_context)
        if configuration.username:
            client.login(configuration.username, configuration.password)
        phase = "send"
        response = client.send_message(message)
        if isinstance(response, dict) and response:
            return _failed("smtp_send_failed")
        provider_message_id = response if isinstance(response, str) and response else None
        return EmailDeliveryResult(
            status="sent",
            provider_message_id=provider_message_id,
            safe_error_code=None,
            sent_at=datetime.now(timezone.utc),
        )
    except Exception:
        return _failed("smtp_send_failed" if phase == "send" else "smtp_connection_failed")
    finally:
        try:
            client.quit()
        except Exception:
            pass
