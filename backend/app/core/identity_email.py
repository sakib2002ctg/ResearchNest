"""Optional SMTP delivery for account-verification and password-reset tokens."""

from __future__ import annotations

import smtplib
import ssl
from email.message import EmailMessage
from email.utils import parseaddr
from typing import Any

from app.core.config import settings


class IdentityEmailDeliveryError(RuntimeError):
    """Raised when configured identity-email delivery cannot complete."""


_PURPOSE_LABELS = {
    "email_verification": "Email verification",
    "password_reset": "Password reset",
}


def _setting(name: str, default: Any = None) -> Any:
    """Read optional SMTP settings without requiring them in local/test config."""
    return getattr(settings, name, default)


def _password_value(password: Any) -> str | None:
    if password is None:
        return None
    getter = getattr(password, "get_secret_value", None)
    value = getter() if callable(getter) else password
    return str(value) if value else None


def _validate_recipient(email: str) -> None:
    name, address = parseaddr(email)
    if name or not address or address != email or "\r" in email or "\n" in email:
        raise ValueError("Invalid identity-email recipient.")


def _message(email: str, token: str, purpose: str, sender: str) -> EmailMessage:
    try:
        label = _PURPOSE_LABELS[purpose]
    except KeyError:
        raise ValueError("Unsupported identity-token purpose.") from None
    if not token or "\r" in token or "\n" in token:
        raise ValueError("Invalid identity token.")

    message = EmailMessage()
    message["From"] = sender
    message["To"] = email
    message["Subject"] = f"ResearchNest {label}"
    message.set_content(
        f"Use this {purpose.replace('_', ' ')} token to continue: {token}\n"
        "This token expires soon and can be used only once."
    )
    return message


def send_identity_token(email: str, token: str, purpose: str) -> None:
    """Send one identity token through configured TLS-protected SMTP.

    SMTP is optional for local and test environments. When ``SMTP_HOST`` is
    unset, the token is intentionally discarded without logging or returning
    plaintext. Once SMTP is configured, authentication and transport failures
    are wrapped without including the token or password in the exception.
    """
    host = _setting("SMTP_HOST")
    if not host:
        return

    try:
        _validate_recipient(email)
        use_ssl = bool(_setting("SMTP_USE_SSL", False))
        port = int(_setting("SMTP_PORT") or (465 if use_ssl else 587))
        username = _setting("SMTP_USERNAME")
        password = _password_value(_setting("SMTP_PASSWORD"))
        sender = _setting("SMTP_FROM") or username or "noreply@localhost"
        if bool(username) != bool(password):
            raise ValueError("SMTP credentials must be configured together.")
        message = _message(email, token, purpose, str(sender))
        context = ssl.create_default_context()

        if use_ssl:
            with smtplib.SMTP_SSL(host, port, timeout=10, context=context) as client:
                client.ehlo()
                if username and password:
                    client.login(str(username), password)
                client.send_message(message)
        else:
            with smtplib.SMTP(host, port, timeout=10) as client:
                client.ehlo()
                client.starttls(context=context)
                client.ehlo()
                if username and password:
                    client.login(str(username), password)
                client.send_message(message)
    except (ValueError, OSError, smtplib.SMTPException):
        raise IdentityEmailDeliveryError("Identity email delivery failed.") from None
