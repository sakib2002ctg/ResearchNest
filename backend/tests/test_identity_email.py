from types import SimpleNamespace

import pytest

from app.core import identity_email
from app.core.identity_email import (
    IdentityEmailDeliveryError,
    send_identity_token,
)


class FakeSMTP:
    instances = []

    def __init__(self, *args, **kwargs):
        self.calls = [("init", args, kwargs)]
        self.message = None
        self.__class__.instances.append(self)

    def __enter__(self):
        self.calls.append(("enter",))
        return self

    def __exit__(self, *exc_info):
        self.calls.append(("exit",))

    def ehlo(self):
        self.calls.append(("ehlo",))

    def starttls(self, context):
        self.calls.append(("starttls", context))

    def login(self, username, password):
        self.calls.append(("login", username, password))

    def send_message(self, message):
        self.calls.append(("send_message",))
        self.message = message


class FailingSMTP(FakeSMTP):
    def starttls(self, context):
        raise OSError("upstream replied with secret-token-value")


@pytest.fixture(autouse=True)
def reset_fake_smtp(monkeypatch):
    FakeSMTP.instances.clear()
    monkeypatch.setattr(
        identity_email,
        "smtplib",
        SimpleNamespace(
            SMTP=FakeSMTP,
            SMTP_SSL=FakeSMTP,
            SMTPException=OSError,
        ),
    )


def configure(monkeypatch, **values):
    defaults = {
        "SMTP_HOST": "smtp.example.test",
        "SMTP_PORT": 587,
        "SMTP_USERNAME": "mailer@example.test",
        "SMTP_PASSWORD": SimpleNamespace(get_secret_value=lambda: "smtp-secret"),
        "SMTP_FROM": "ResearchNest <mailer@example.test>",
        "SMTP_USE_SSL": False,
    }
    defaults.update(values)
    monkeypatch.setattr(identity_email, "settings", SimpleNamespace(**defaults))


def test_no_smtp_configuration_is_a_noop(monkeypatch):
    configure(monkeypatch, SMTP_HOST=None)

    send_identity_token("user@example.test", "token-value", "password_reset")
    assert FakeSMTP.instances == []


def test_starttls_is_required_before_authentication_and_send(monkeypatch):
    configure(monkeypatch)

    send_identity_token("user@example.test", "token-value", "email_verification")

    smtp = FakeSMTP.instances[0]
    names = [call[0] for call in smtp.calls]
    assert names.index("starttls") < names.index("login") < names.index("send_message")
    assert smtp.calls[names.index("login")][2] == "smtp-secret"
    assert smtp.message["To"] == "user@example.test"
    assert "token-value" in smtp.message.get_content()


def test_implicit_tls_uses_smtp_ssl_and_does_not_downgrade(monkeypatch):
    configure(monkeypatch, SMTP_PORT=465, SMTP_USE_SSL=True)

    send_identity_token("user@example.test", "token-value", "password_reset")

    smtp = FakeSMTP.instances[0]
    init = smtp.calls[0]
    assert init[0] == "init" and init[1][1] == 465
    assert "starttls" not in [call[0] for call in smtp.calls]
    assert any(call[0] == "send_message" for call in smtp.calls)


def test_delivery_failure_does_not_expose_token_or_password(monkeypatch):
    configure(monkeypatch)
    monkeypatch.setattr(identity_email.smtplib, "SMTP", FailingSMTP)
    secret_token = "secret-token-value"
    with pytest.raises(IdentityEmailDeliveryError) as raised:
        send_identity_token("user@example.test", secret_token, "password_reset")
    assert secret_token not in str(raised.value) and "smtp-secret" not in str(
        raised.value
    )
    assert raised.value.__suppress_context__


def test_invalid_purpose_and_header_values_are_rejected(monkeypatch):
    configure(monkeypatch)
    with pytest.raises(
        IdentityEmailDeliveryError, match="Identity email delivery failed"
    ):
        send_identity_token("user@example.test", "token-value", "other")
    with pytest.raises(
        IdentityEmailDeliveryError, match="Identity email delivery failed"
    ):
        send_identity_token(
            "attacker@example.test\r\nBcc: victim@example.test",
            "token",
            "password_reset",
        )
