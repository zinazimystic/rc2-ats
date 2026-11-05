"""Outgoing email over SMTP (verification codes). Never logs credentials or message bodies."""
from __future__ import annotations

import html
import logging
import smtplib
import ssl
from email.message import EmailMessage
from email.utils import formataddr, make_msgid

from app.core.config import settings

log = logging.getLogger("app.mailer")


class EmailDeliveryError(Exception):
    """The SMTP server rejected the message or could not be reached."""


def _connect() -> smtplib.SMTP:
    host, port, timeout = settings.smtp_host, settings.smtp_port, settings.smtp_timeout_seconds
    ctx = ssl.create_default_context()
    if settings.smtp_security == "ssl":
        server: smtplib.SMTP = smtplib.SMTP_SSL(host, port, timeout=timeout, context=ctx)
    else:
        server = smtplib.SMTP(host, port, timeout=timeout)
        server.ehlo()
        if settings.smtp_security == "starttls":
            server.starttls(context=ctx)
            server.ehlo()
    server.login(settings.smtp_user, settings.smtp_password)
    return server


def send_email(to: str, subject: str, text: str, html_body: str | None = None) -> None:
    """Send one email. Raises EmailDeliveryError with a safe message on any failure."""
    if not settings.smtp_enabled:
        raise EmailDeliveryError("Email sending is not configured")
    msg = EmailMessage()
    msg["From"] = formataddr((settings.smtp_from_name, settings.smtp_from_email))
    msg["To"] = to
    msg["Subject"] = subject
    msg["Message-ID"] = make_msgid(domain=settings.smtp_from_email.split("@")[-1])
    msg.set_content(text)
    if html_body:
        msg.add_alternative(html_body, subtype="html")
    try:
        with _connect() as server:
            refused = server.send_message(msg)
        if refused:
            raise EmailDeliveryError("The recipient address was refused")
    except EmailDeliveryError:
        raise
    except (smtplib.SMTPException, OSError, ssl.SSLError) as exc:
        log.warning("SMTP delivery failed: %s: %s", type(exc).__name__, str(exc)[:160])
        raise EmailDeliveryError("The email server could not deliver the message") from exc


def verification_email(name: str, code: str, minutes: int) -> tuple[str, str, str]:
    """(subject, plain text, html) for the 6-digit email verification code."""
    first = (name or "there").split()[0]
    subject = f"{code} is your verification code"
    text = (
        f"Hi {first},\n\nYour RC3 Talent Intelligence verification code is {code}.\n"
        f"It expires in {minutes} minutes. If you didn't request it, you can ignore this email.\n"
    )
    digits = "".join(
        f'<span style="display:inline-block;width:42px;height:52px;line-height:52px;margin:0 4px;border-radius:12px;'
        f'background:#eef3ff;color:#1d4ed8;font-size:26px;font-weight:700;font-family:Segoe UI,Arial,sans-serif">{html.escape(d)}</span>'
        for d in code
    )
    body = f"""<!doctype html><html><body style="margin:0;background:#f4f6fb;padding:32px 12px;font-family:Segoe UI,Arial,sans-serif;color:#0f172a">
<table role="presentation" align="center" width="100%" style="max-width:480px;background:#ffffff;border-radius:20px;padding:32px;border:1px solid #e5e9f2">
<tr><td style="font-size:14px;font-weight:700;color:#2f6bff;letter-spacing:.4px">RC3 TALENT INTELLIGENCE</td></tr>
<tr><td style="font-size:22px;font-weight:700;padding-top:12px">Verify your email</td></tr>
<tr><td style="font-size:15px;line-height:1.6;color:#475569;padding-top:10px">Hi {html.escape(first)}, enter this code to confirm your email address.</td></tr>
<tr><td align="center" style="padding:24px 0">{digits}</td></tr>
<tr><td style="font-size:13px;line-height:1.6;color:#64748b">This code expires in {minutes} minutes. If you didn't request it, you can safely ignore this email.</td></tr>
</table></body></html>"""
    return subject, text, body
