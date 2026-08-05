from datetime import timezone
from email.message import EmailMessage

import pytest

from app.config import get_email_delivery_settings
from app.services import email_delivery
from app.services.email_delivery import (
    EmailDeliveryError,
    send_email,
    validate_email_configuration,
    validate_recipient,
)


SMTP_ENV_KEYS = (
    "APP_ENV",
    "EMAIL_DELIVERY_ENABLED",
    "SMTP_HOST",
    "SMTP_PORT",
    "SMTP_USERNAME",
    "SMTP_PASSWORD",
    "SMTP_FROM_EMAIL",
    "SMTP_FROM_NAME",
    "SMTP_USE_TLS",
    "SMTP_USE_SSL",
    "SMTP_TIMEOUT_SECONDS",
    "PUBLIC_APP_URL",
    "PORTAL_TOKEN_SECRET",
)


@pytest.fixture
def valid_smtp_env(monkeypatch):
    for key in SMTP_ENV_KEYS:
        monkeypatch.delenv(key, raising=False)
    values = {
        "APP_ENV": "local",
        "EMAIL_DELIVERY_ENABLED": "true",
        "SMTP_HOST": "smtp.example.test",
        "SMTP_PORT": "587",
        "SMTP_USERNAME": "mailer",
        "SMTP_PASSWORD": "smtp-secret-value",
        "SMTP_FROM_EMAIL": "contracts@example.test",
        "SMTP_FROM_NAME": "ContractOps AI",
        "SMTP_USE_TLS": "true",
        "SMTP_USE_SSL": "false",
        "SMTP_TIMEOUT_SECONDS": "10",
        "PUBLIC_APP_URL": "http://localhost:3000",
        "PORTAL_TOKEN_SECRET": "portal-secret-value",
    }
    for key, value in values.items():
        monkeypatch.setenv(key, value)
    return values


class RecordingSMTP:
    def __init__(self, host, port, timeout):
        self.connection = (host, port, timeout)
        self.started_tls = False
        self.tls_context = None
        self.login_args = None
        self.message = None

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return None

    def starttls(self, *, context):
        self.started_tls = True
        self.tls_context = context

    def login(self, username, password):
        self.login_args = (username, password)

    def send_message(self, message):
        self.message = message
        return {}


def test_send_email_delivers_text_and_html_through_injected_smtp(monkeypatch, valid_smtp_env):
    clients = []
    tls_context = object()
    monkeypatch.setattr(email_delivery.ssl, "create_default_context", lambda: tls_context)

    def smtp_factory(*args, **kwargs):
        client = RecordingSMTP(*args, **kwargs)
        clients.append(client)
        return client

    result = send_email(
        recipient="reviewer@example.test",
        subject="Contract review requested",
        text_body="Open the secure review link.",
        html_body="<p>Open the secure review link.</p>",
        smtp_factory=smtp_factory,
    )

    assert result.status == "sent"
    assert result.provider_message_id is None
    assert result.safe_error_code is None
    assert result.sent_at.tzinfo is timezone.utc
    assert len(clients) == 1
    client = clients[0]
    assert client.connection == ("smtp.example.test", 587, 10.0)
    assert client.started_tls is True
    assert client.tls_context is tls_context
    assert client.login_args == ("mailer", "smtp-secret-value")
    assert isinstance(client.message, EmailMessage)
    assert client.message["To"] == "reviewer@example.test"
    assert client.message["From"] == "ContractOps AI <contracts@example.test>"
    assert client.message.get_body(preferencelist=("plain",)).get_content().strip() == "Open the secure review link."
    assert client.message.get_body(preferencelist=("html",)).get_content().strip() == (
        "<p>Open the secure review link.</p>"
    )


@pytest.mark.parametrize(
    "recipient",
    [
        "",
        "not-an-email",
        "Name <missing-at-sign>",
        "one@example.test, two@example.test",
        "a@example.test\nBcc: x@y.test",
        ".user@example.test",
        "user.@example.test",
        "user..name@example.test",
        "user@example..test",
        "user@-example.test",
        "user@example-.test",
        "user@exam_ple.test",
        f"user@{'a' * 64}.test",
    ],
)
def test_validate_recipient_rejects_invalid_or_multiple_addresses(recipient):
    with pytest.raises(EmailDeliveryError) as exc_info:
        validate_recipient(recipient)
    assert (exc_info.value.status_code, exc_info.value.code) == (422, "invalid_email_recipient")


def test_validate_recipient_accepts_conservative_single_mailbox():
    assert validate_recipient("user.name+tag@example-domain.test") == "user.name+tag@example-domain.test"


def test_disabled_delivery_is_rejected(monkeypatch, valid_smtp_env):
    monkeypatch.setenv("EMAIL_DELIVERY_ENABLED", "false")
    with pytest.raises(EmailDeliveryError) as exc_info:
        validate_email_configuration()
    assert (exc_info.value.status_code, exc_info.value.code) == (503, "email_delivery_disabled")


def test_configuration_validation_does_not_return_credentials(valid_smtp_env):
    assert validate_email_configuration() is None


def test_tls_and_ssl_conflict_is_rejected(monkeypatch, valid_smtp_env):
    monkeypatch.setenv("SMTP_USE_SSL", "true")
    with pytest.raises(EmailDeliveryError) as exc_info:
        validate_email_configuration()
    assert exc_info.value.code == "smtp_tls_ssl_conflict"


@pytest.mark.parametrize("key", ["SMTP_HOST", "SMTP_PORT", "SMTP_FROM_EMAIL", "PORTAL_TOKEN_SECRET"])
def test_enabled_delivery_requires_configuration(monkeypatch, valid_smtp_env, key):
    monkeypatch.setenv(key, "")
    with pytest.raises(EmailDeliveryError) as exc_info:
        validate_email_configuration()
    assert exc_info.value.code == "smtp_configuration_missing"


@pytest.mark.parametrize("timeout", ["0", "-1", "61", "nan", "not-a-number"])
def test_timeout_must_be_positive_and_bounded(monkeypatch, valid_smtp_env, timeout):
    monkeypatch.setenv("SMTP_TIMEOUT_SECONDS", timeout)
    with pytest.raises(EmailDeliveryError) as exc_info:
        validate_email_configuration()
    assert exc_info.value.code == "smtp_timeout_invalid"


def test_smtp_ssl_receives_default_tls_context(monkeypatch, valid_smtp_env):
    monkeypatch.setenv("SMTP_USE_TLS", "false")
    monkeypatch.setenv("SMTP_USE_SSL", "true")
    tls_context = object()
    monkeypatch.setattr(email_delivery.ssl, "create_default_context", lambda: tls_context)
    clients = []

    class RecordingSMTPSsl(RecordingSMTP):
        def __init__(self, host, port, timeout, context):
            super().__init__(host, port, timeout)
            self.ssl_context = context

    def smtp_factory(*args, **kwargs):
        client = RecordingSMTPSsl(*args, **kwargs)
        clients.append(client)
        return client

    result = send_email(
        recipient="reviewer@example.test",
        subject="Contract review requested",
        text_body="Open the secure review link.",
        html_body="<p>Open the secure review link.</p>",
        smtp_factory=smtp_factory,
    )

    assert result.status == "sent"
    assert clients[0].ssl_context is tls_context
    assert clients[0].started_tls is False


def test_smtp_username_is_hidden_from_configuration_repr(valid_smtp_env):
    assert valid_smtp_env["SMTP_USERNAME"] not in repr(get_email_delivery_settings())


@pytest.mark.parametrize(
    ("app_env", "public_url"),
    [
        ("demo", "http://contracts.example.test"),
        ("production", "https://localhost:3000"),
        ("production", "https://127.0.0.1"),
    ],
)
def test_demo_and_production_require_public_https_url(monkeypatch, valid_smtp_env, app_env, public_url):
    monkeypatch.setenv("APP_ENV", app_env)
    monkeypatch.setenv("PUBLIC_APP_URL", public_url)
    with pytest.raises(EmailDeliveryError) as exc_info:
        validate_email_configuration()
    assert exc_info.value.code == "public_app_url_invalid"


@pytest.mark.parametrize(
    ("failure_method", "safe_code"),
    [
        ("connect", "smtp_connection_failed"),
        ("send", "smtp_send_failed"),
    ],
)
def test_smtp_failures_return_only_safe_metadata(valid_smtp_env, failure_method, safe_code):
    secret = valid_smtp_env["SMTP_PASSWORD"]

    if failure_method == "connect":
        def smtp_factory(*_args, **_kwargs):
            raise OSError(f"could not connect using {secret}")
    else:
        class FailingSMTP(RecordingSMTP):
            def send_message(self, _message):
                raise RuntimeError(f"provider rejected password {secret}")

        smtp_factory = FailingSMTP

    result = send_email(
        recipient="reviewer@example.test",
        subject="Contract review requested",
        text_body="Open the secure review link.",
        html_body="<p>Open the secure review link.</p>",
        smtp_factory=smtp_factory,
    )

    assert result.status == "failed"
    assert result.provider_message_id is None
    assert result.safe_error_code == safe_code
    assert result.sent_at is None
    assert secret not in repr(result)
    assert secret not in str(result)


def test_validation_error_does_not_expose_credentials(monkeypatch, valid_smtp_env):
    secret = valid_smtp_env["SMTP_PASSWORD"]
    monkeypatch.setenv("SMTP_PORT", secret)
    with pytest.raises(EmailDeliveryError) as exc_info:
        validate_email_configuration()
    assert exc_info.value.code == "smtp_configuration_invalid"
    assert secret not in str(exc_info.value)
    assert secret not in repr(exc_info.value)
