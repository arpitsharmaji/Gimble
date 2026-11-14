import logging, smtplib
from email.message import EmailMessage
from .config import settings

log = logging.getLogger("gimble.mail")


def send_email(to: str, subject: str, body: str) -> bool:
    """Send via SMTP when configured, otherwise print to the server log (development)."""
    if not settings.SMTP_HOST:
        log.warning("EMAIL (not sent - SMTP not configured)\nTo: %s\nSubject: %s\n%s", to, subject, body)
        return False
    msg = EmailMessage()
    msg["From"], msg["To"], msg["Subject"] = settings.MAIL_FROM, to, subject
    msg.set_content(body)
    try:
        with smtplib.SMTP(settings.SMTP_HOST, settings.SMTP_PORT, timeout=15) as s:
            s.starttls()
            if settings.SMTP_USER:
                s.login(settings.SMTP_USER, settings.SMTP_PASSWORD)
            s.send_message(msg)
        return True
    except Exception:
        log.exception("Failed to send email to %s", to)
        return False
